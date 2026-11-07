"""Transparent tailor matching: hard filters on declared data, then explainable ranking.

Ranking is only a suggestion; the buyer chooses, and a tailor's acceptance is a separate step.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, NotFound
from app.models import (
    Customization,
    FabricListing,
    TailorCapability,
    TailorProfile,
    TemplateVersion,
)
from app.services.customization import get_revision


def _problems(listing: FabricListing, defn: dict, state: dict, tailor: TailorProfile,
              cap: TailorCapability | None, address: dict) -> list[str]:
    if tailor.status != "active":
        return ["Tailor tidak aktif"]
    if cap is None:
        return ["Tailor belum mendukung template ini"]
    problems = []
    material = (listing.material or "").lower()
    if cap.materials and not any(m.lower() in material or material in m.lower()
                                 for m in cap.materials if material):
        problems.append(f"Material '{listing.material}' tidak termasuk yang dilayani tailor")
    for field, value in state.items():
        spec = defn["options"].get(field)
        if spec is None or value == spec["default"]:
            continue
        declared = cap.supported_options.get(field)
        if declared is not None and value not in declared:
            problems.append(f"Opsi {field}={value} tidak didukung tailor")
    area = [a.strip().lower() for a in tailor.service_area]
    if area and address["province"].strip().lower() not in area and \
            address["city"].strip().lower() not in area:
        problems.append("Alamat tujuan di luar wilayah layanan tailor")
    if cap.weekly_capacity < 1:
        problems.append("Kapasitas tailor tidak tersedia")
    return problems


def _context(session: Session, cust: Customization):
    listing = session.get(FabricListing, cust.listing_id)
    defn = session.get(TemplateVersion, cust.template_version_id).definition
    state = get_revision(session, cust, cust.current_revision).state
    return listing, defn, state


def recommendations(session: Session, cust: Customization, address: dict) -> list[dict]:
    listing, defn, state = _context(session, cust)
    rows = session.execute(
        select(TailorProfile, TailorCapability)
        .join(TailorCapability, TailorCapability.tailor_id == TailorProfile.id)
        .where(TailorCapability.template_code == cust.template_code)).all()
    ranked = []
    for tailor, cap in rows:
        if _problems(listing, defn, state, tailor, cap, address):
            continue
        same_province = tailor.province.strip().lower() == address["province"].strip().lower()
        reasons = [f"Mendukung template {cust.template_code}",
                   f"Lead time {cap.lead_time_days} hari (deklarasi tailor)",
                   f"Tarif dasar Rp {cap.base_rate_idr:,} (deklarasi tailor)".replace(",", ".")]
        if cap.materials:
            reasons.append("Melayani material: " + ", ".join(cap.materials))
        if same_province:
            reasons.append(f"Berada di provinsi yang sama dengan tujuan ({tailor.province})")
        ranked.append(((not same_province, cap.lead_time_days, cap.base_rate_idr), {
            "tailor_id": tailor.id, "shop_name": tailor.shop_name, "city": tailor.city,
            "province": tailor.province, "experience_years": tailor.experience_years,
            "base_rate_idr": cap.base_rate_idr, "lead_time_days": cap.lead_time_days,
            "weekly_capacity": cap.weekly_capacity, "reasons": reasons, "verified": True}))
    ranked.sort(key=lambda t: t[0])
    return [r for _, r in ranked]


def assert_eligible(session: Session, cust: Customization, tailor_id: uuid.UUID,
                    address: dict) -> TailorProfile:
    tailor = session.get(TailorProfile, tailor_id)
    if tailor is None:
        raise NotFound("Tailor not found")
    listing, defn, state = _context(session, cust)
    cap = session.scalar(select(TailorCapability).where(
        TailorCapability.tailor_id == tailor.id, TailorCapability.template_code == cust.template_code))
    problems = _problems(listing, defn, state, tailor, cap, address)
    if problems:
        raise AppValidationError("; ".join(problems), field="tailor_id")
    return tailor
