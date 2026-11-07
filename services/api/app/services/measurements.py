import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, NotFound
from app.core.revision import check_revision
from app.models import Customization, MeasurementSet, MeasurementValue, User
from app.services import audit

# key -> (min cm, max cm): plausible adult ranges; anything else is rejected, never guessed.
DIMENSION_RANGES = {
    "chest_circumference": (50, 200), "waist_circumference": (40, 200),
    "hip_circumference": (50, 220), "shoulder_width": (25, 70), "back_length": (25, 90),
    "sleeve_length": (5, 90), "neck_circumference": (25, 60),
}
HEIGHT_RANGE = (100, 230)


def _q(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _check_value(key: str, value) -> Decimal:
    if key not in DIMENSION_RANGES:
        raise AppValidationError(f"Dimensi '{key}' tidak dikenal", field=f"values.{key}")
    lo, hi = DIMENSION_RANGES[key]
    try:
        number = _q(value)
    except (InvalidOperation, ValueError):
        raise AppValidationError(f"'{key}' harus berupa angka (cm)", field=f"values.{key}") from None
    if not (lo <= number <= hi):
        raise AppValidationError(f"'{key}' harus antara {lo} dan {hi} cm", field=f"values.{key}")
    return number


def _check_height(height) -> Decimal | None:
    if height is None:
        return None
    number = _q(height)
    if not (HEIGHT_RANGE[0] <= number <= HEIGHT_RANGE[1]):
        raise AppValidationError(f"Tinggi harus antara {HEIGHT_RANGE[0]} dan {HEIGHT_RANGE[1]} cm",
                                 field="height_cm")
    return number


def owned_set(session: Session, user: User, set_id: uuid.UUID) -> MeasurementSet:
    mset = session.get(MeasurementSet, set_id)
    if mset is None or mset.owner_id != user.id:
        raise NotFound("Measurement set not found")
    return mset


def _values(session: Session, mset: MeasurementSet) -> dict[str, MeasurementValue]:
    return {v.key: v for v in session.scalars(
        select(MeasurementValue).where(MeasurementValue.set_id == mset.id))}


def create_set(session: Session, user: User, height_cm, values: dict) -> MeasurementSet:
    mset = MeasurementSet(owner_id=user.id, height_cm=_check_height(height_cm))
    session.add(mset)
    session.flush()
    _write(session, user, mset, values, creating=True)
    audit.record(session, actor=user, action="measurements.created", target_type="measurement_set",
                 target_id=mset.id)
    return mset


def _write(session: Session, user: User, mset: MeasurementSet, values: dict, *, creating: bool) -> None:
    existing = _values(session, mset)
    now = datetime.now(UTC).isoformat()
    for key, raw in values.items():
        number = None if raw is None else _check_value(key, raw)
        if key not in DIMENSION_RANGES:
            raise AppValidationError(f"Dimensi '{key}' tidak dikenal", field=f"values.{key}")
        row = existing.get(key)
        if row is None:
            session.add(MeasurementValue(
                set_id=mset.id, key=key, value_cm=number,
                source="manual_required" if number is None else "manual",
                history=[{"at": now, "by": str(user.id), "from": None,
                          "to": None if number is None else str(number)}]))
            continue
        history = list(row.history)
        history.append({"at": now, "by": str(user.id),
                        "from": None if row.value_cm is None else str(row.value_cm),
                        "to": None if number is None else str(number)})
        if number is None:
            row.value_cm, row.source = None, "manual_required"
        else:
            if row.source == "estimated" and row.original_value_cm is None:
                row.original_value_cm = row.value_cm  # keep the model's original estimate
            row.source = "corrected" if row.original_value_cm is not None else "manual"
            row.value_cm = number
        row.history = history
    session.flush()


def patch_set(session: Session, user: User, mset: MeasurementSet, expected_revision: int,
              values: dict, height_cm) -> MeasurementSet:
    check_revision(expected_revision, mset.revision)
    if height_cm is not None:
        mset.height_cm = _check_height(height_cm)
    _write(session, user, mset, values, creating=False)
    mset.revision += 1
    mset.status, mset.confirmed_at = "draft", None  # any edit needs reconfirmation
    session.flush()
    audit.record(session, actor=user, action="measurements.corrected", target_type="measurement_set",
                 target_id=mset.id, metadata={"keys": sorted(values)})
    return mset


def missing_required(session: Session, mset: MeasurementSet, defn: dict) -> list[str]:
    rows = _values(session, mset)
    return [k for k in defn["required_dimensions"] if k not in rows or rows[k].value_cm is None]


def attach(session: Session, user: User, cust: Customization, set_id: uuid.UUID) -> MeasurementSet:
    mset = owned_set(session, user, set_id)
    cust.measurement_set_id = mset.id
    session.flush()
    return mset


def confirm_set(session: Session, user: User, mset: MeasurementSet, defn: dict) -> MeasurementSet:
    missing = missing_required(session, mset, defn)
    if missing:
        raise AppValidationError("Dimensi wajib belum lengkap: " + ", ".join(missing),
                                 field="measurements")
    mset.status, mset.confirmed_at = "confirmed", datetime.now(UTC)
    session.flush()
    audit.record(session, actor=user, action="measurements.confirmed", target_type="measurement_set",
                 target_id=mset.id)
    return mset


def set_out(session: Session, mset: MeasurementSet) -> dict:
    rows = _values(session, mset)
    return {
        "id": mset.id, "height_cm": mset.height_cm, "status": mset.status,
        "revision": mset.revision, "confirmed_at": mset.confirmed_at,
        "values": [{"key": k, "value_cm": r.value_cm, "source": r.source,
                    "original_value_cm": r.original_value_cm, "quality_flag": r.quality_flag,
                    "model_version": r.model_version, "history": r.history}
                   for k, r in sorted(rows.items())],
        "notice": ("Ukuran adalah titik awal. Ukuran badan berbeda dari ukuran baju jadi; "
                   "penjahit menetapkan dimensi produksi."),
    }
