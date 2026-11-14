import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FabricListing, GarmentTemplate, TemplateVersion, User
from app.services import audit, motif_layout
from app.services.template_defs import DEFINITIONS, definition


def _hash(defn: dict) -> str:
    return hashlib.sha256(json.dumps(defn, sort_keys=True).encode()).hexdigest()


def sync_templates(session: Session, admin: User | None = None) -> list[dict]:
    """Idempotently load T01-T05. A changed definition becomes a new template version."""
    out = []
    for code in sorted(DEFINITIONS):
        defn = definition(code)
        template = session.get(GarmentTemplate, code)
        if template is None:
            template = GarmentTemplate(code=code, name=defn["name"])
            session.add(template)
            session.flush()
        latest = latest_version(session, code)
        digest = _hash(defn)
        created = False
        if latest is None or latest.definition_hash != digest:
            latest = TemplateVersion(code=code, version=(latest.version + 1) if latest else 1,
                                     definition=defn, definition_hash=digest)
            session.add(latest)
            session.flush()
            created = True
            audit.record(session, actor=admin, action="template.version_created",
                         target_type="garment_template", target_id=code,
                         metadata={"version": latest.version})
        out.append({"code": code, "version": latest.version, "created": created})
    return out


def latest_version(session: Session, code: str) -> TemplateVersion | None:
    return session.scalar(select(TemplateVersion).where(TemplateVersion.code == code)
                          .order_by(TemplateVersion.version.desc()).limit(1))


def list_templates(session: Session) -> list[dict]:
    rows = session.scalars(select(GarmentTemplate).where(GarmentTemplate.active)
                           .order_by(GarmentTemplate.code))
    out = []
    for t in rows:
        v = latest_version(session, t.code)
        if v:
            out.append(template_out(t, v))
    return out


def template_out(template: GarmentTemplate, version: TemplateVersion) -> dict:
    d = version.definition
    return {"code": template.code, "name": template.name, "version": version.version,
            "base_cut": d["base_cut"], "required_dimensions": d["required_dimensions"],
            "options": d["options"], "preview": d["preview"],
            "notice": d["demo_values_notice"]}


def compatibility(session: Session, listing: FabricListing) -> list[dict]:
    """Per-template compatibility with an exact listing, with human-readable reasons."""
    results = []
    for code in sorted(DEFINITIONS):
        version = latest_version(session, code)
        if version is None:
            continue
        rules = version.definition["material_rules"]
        reasons = []
        if not listing.material:
            reasons.append("Data material kain belum diisi merchant")
        width = listing.usable_width_cm if listing.selling_unit == "meter" else listing.piece_width_cm
        if not width:
            reasons.append("Lebar kain yang dapat dipakai belum diisi merchant")
        elif width < rules["min_fabric_width_cm"]:
            reasons.append(f"Lebar kain {width} cm kurang dari minimal "
                           f"{rules['min_fabric_width_cm']} cm untuk template ini")
        if listing.selling_unit == "piece" and not listing.piece_length_cm:
            reasons.append("Panjang potongan kain belum diisi merchant")
        results.append({"code": code, "name": version.definition["name"],
                        "version": version.version, "compatible": not reasons, "reasons": reasons})
    return results


def validate_value(defn: dict, field: str, value, listing: FabricListing):
    """Return the normalised value or raise ValueError(reason). Server-side source of truth."""
    spec = defn["options"].get(field)
    if spec is None:
        raise ValueError(f"Template ini tidak memiliki opsi '{field}'")
    if spec["type"] == "layout":
        return motif_layout.check(spec, value)
    if spec["type"] == "enum":
        if value not in spec["values"]:
            raise ValueError(f"Nilai '{value}' tidak didukung; pilihan: {', '.join(spec['values'])}")
        allowed = spec.get("requires_material_in")
        if allowed and value != spec["default"]:
            material = (listing.material or "").lower()
            if not any(m in material for m in allowed):
                raise ValueError(f"Opsi '{value}' tidak cocok dengan material "
                                 f"'{listing.material or 'tidak diketahui'}'")
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' harus berupa angka") from None
    if not (spec["min"] <= number <= spec["max"]):
        raise ValueError(f"'{field}' harus antara {spec['min']} dan {spec['max']} {spec['unit']}")
    return int(number) if number == int(number) else round(number, 1)
