"""Deterministic fabric requirement estimator (no language-model arithmetic)."""
import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError
from app.models import (
    Customization,
    FabricListing,
    MaterialEstimate,
    MeasurementSet,
    MeasurementValue,
    User,
)
from app.services import audit
from app.services.commerce import can_fulfill
from app.services.customization import definition_of, get_revision
from app.services.measurements import missing_required


def compute(defn: dict, dims: dict[str, float], state: dict, *, width_cm: float,
            pattern_repeat_cm: float | None) -> dict:
    """Required fabric (cm) for one garment. Pure function; `fits` False when width is too narrow."""
    rules = defn["material_rules"]
    ease, seam, hem = rules["ease_cm"], rules["seam_allowance_cm"], rules["hem_allowance_cm"]
    chest = dims["chest_circumference"]
    panel_w = (chest + ease) / 2 + 2 * seam
    notes = [f"Kelonggaran (ease) {ease} cm dan kampuh {seam} cm per sisi (nilai demo template)",
             f"Lebar panel badan {panel_w:.1f} cm"]
    if width_cm < panel_w:
        return {"fits": False, "reason": f"Lebar kain {width_cm:.0f} cm tidak cukup untuk lebar "
                                         f"panel {panel_w:.0f} cm", "assumptions": notes}
    body_len = dims["back_length"] + (state.get("hem_length_delta_cm", 0) or 0) + hem
    side_by_side = 2 * panel_w <= width_cm
    body_cut = body_len if side_by_side else 2 * body_len
    notes.append("Panel depan dan belakang dipotong berdampingan" if side_by_side
                 else "Panel depan dan belakang dipotong berurutan karena kain kurang lebar")
    sleeves_cut = 0.0
    if rules["sleeve_width_ratio"] > 0 and "sleeve_length" in dims:
        sleeve_len = dims["sleeve_length"] + (state.get("sleeve_length_delta_cm", 0) or 0) + hem
        sleeve_w = rules["sleeve_width_ratio"] * chest + 2 * seam
        if sleeve_w > width_cm:
            return {"fits": False, "reason": "Lebar kain tidak cukup untuk lengan",
                    "assumptions": notes}
        sleeves_cut = sleeve_len if 2 * sleeve_w <= width_cm else 2 * sleeve_len
        leftover = width_cm - (2 * panel_w if side_by_side else panel_w)
        if leftover >= 2 * sleeve_w and sleeve_len <= body_cut:
            sleeves_cut = 0.0
            notes.append("Lengan ditempatkan di samping panel badan")
    extras = 0.0
    for option, table in rules["option_extra_cm"].items():
        extras += table.get(str(state.get(option)), 0)
    total = body_cut + sleeves_cut + extras
    if pattern_repeat_cm:
        total = math.ceil(total / pattern_repeat_cm) * pattern_repeat_cm
        notes.append(f"Dibulatkan ke kelipatan pengulangan motif {pattern_repeat_cm:.0f} cm")
    return {"fits": True, "required_length_cm": round(total, 1),
            "breakdown_cm": {"body": round(body_cut, 1), "sleeves": round(sleeves_cut, 1),
                             "options": round(extras, 1)}, "assumptions": notes}


def _purchase_meter(listing: FabricListing, required_cm: float) -> Decimal:
    required = Decimal(str(round(required_cm / 100, 2)))
    if required <= listing.min_quantity:
        return listing.min_quantity
    steps = math.ceil((required - listing.min_quantity) / listing.quantity_increment)
    return listing.min_quantity + steps * listing.quantity_increment


def estimate_for(session: Session, user: User, cust: Customization) -> MaterialEstimate:
    if cust.measurement_set_id is None:
        raise AppValidationError("Lampirkan set ukuran badan terlebih dahulu", field="measurements")
    defn = definition_of(session, cust)
    mset = session.get(MeasurementSet, cust.measurement_set_id)
    missing = missing_required(session, mset, defn)
    if missing:
        raise AppValidationError("Dimensi wajib belum lengkap: " + ", ".join(missing),
                                 field="measurements")
    listing = session.get(FabricListing, cust.listing_id)
    dims = {v.key: float(v.value_cm) for v in session.scalars(
        select(MeasurementValue).where(MeasurementValue.set_id == mset.id)) if v.value_cm is not None}
    state = get_revision(session, cust, cust.current_revision).state
    width = listing.usable_width_cm if listing.selling_unit == "meter" else listing.piece_width_cm
    if not width or not listing.material:
        raise AppValidationError("Data material/lebar listing belum lengkap untuk estimasi kustom",
                                 field="listing")
    result = compute(defn, dims, state, width_cm=float(width),
                     pattern_repeat_cm=float(listing.pattern_repeat_cm) if listing.pattern_repeat_cm else None)
    result["tailor_validation_required"] = True
    result["selling_unit"] = listing.selling_unit
    if result["fits"]:
        required_cm = result["required_length_cm"]
        if listing.selling_unit == "meter":
            qty = _purchase_meter(listing, required_cm)
            result.update(purchase_quantity=str(qty),
                          required_continuous_cut_m=round(required_cm / 100, 2),
                          surplus_m=str(qty - Decimal(str(round(required_cm / 100, 2)))))
            result["stock_ok"] = can_fulfill(session, listing, qty)
        else:
            pieces = math.ceil(required_cm / listing.piece_length_cm)
            result.update(purchase_quantity=str(pieces),
                          surplus_cm=round(pieces * listing.piece_length_cm - required_cm, 1))
            result["stock_ok"] = can_fulfill(session, listing, Decimal(pieces))
    else:
        result["stock_ok"] = False
    for old in session.scalars(select(MaterialEstimate).where(
            MaterialEstimate.customization_id == cust.id, MaterialEstimate.status == "current")):
        old.status = "superseded"
    est = MaterialEstimate(customization_id=cust.id, design_revision=cust.current_revision,
                           measurement_set_id=mset.id, measurement_revision=mset.revision,
                           listing_revision=listing.revision, result=result)
    session.add(est)
    session.flush()
    audit.record(session, actor=user, action="material.estimated", target_type="customization",
                 target_id=cust.id, metadata={"design_revision": cust.current_revision})
    return est


def stale_reasons(session: Session, cust: Customization, est: MaterialEstimate) -> list[str]:
    reasons = []
    if est.design_revision != cust.current_revision:
        reasons.append("design_revision_changed")
    mset = session.get(MeasurementSet, cust.measurement_set_id) if cust.measurement_set_id else None
    if mset is None or est.measurement_set_id != mset.id or est.measurement_revision != mset.revision:
        reasons.append("measurements_changed")
    listing = session.get(FabricListing, cust.listing_id)
    if est.listing_revision != listing.revision:
        reasons.append("listing_changed")
    return reasons


def current_estimate(session: Session, cust: Customization) -> MaterialEstimate | None:
    return session.scalar(select(MaterialEstimate).where(
        MaterialEstimate.customization_id == cust.id, MaterialEstimate.status == "current")
        .order_by(MaterialEstimate.created_at.desc()).limit(1))


def estimate_out(session: Session, cust: Customization, est: MaterialEstimate) -> dict:
    reasons = stale_reasons(session, cust, est)
    return {"id": est.id, "design_revision": est.design_revision, "result": est.result,
            "stale": bool(reasons), "stale_reasons": reasons, "created_at": est.created_at,
            "notice": "Estimasi awal; penjahit memvalidasi kebutuhan kain final."}
