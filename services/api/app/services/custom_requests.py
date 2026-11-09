import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AppValidationError,
    Forbidden,
    InsufficientStock,
    InvalidTransition,
    NotFound,
)
from app.models import (
    Customization,
    DeliveryAddress,
    FabricListing,
    File,
    MaterialEstimate,
    MeasurementSet,
    MeasurementValue,
    MerchantConfirmation,
    MerchantProfile,
    Preview,
    ProductionSpec,
    Quote,
    QuoteLine,
    TailorCapability,
    TailorProfile,
    User,
)
from app.models.custom import CustomRequest
from app.services import audit, matching
from app.services import commerce as commerce_svc
from app.services import customization as cust_svc
from app.services import listings as listings_svc
from app.services import material as material_svc
from app.services.partners import active_merchant, active_tailor
from app.services.pricing import line_subtotal, validate_quantity
from app.services.shipping import estimate as shipping_estimate
from app.services.signing import make_token

PREVIEW_LABEL = "Ilustrasi konseptual; bukan pola potong atau jaminan hasil akhir."

OPEN_STATES = ("draft", "submitted", "validating", "ready_for_quote", "awaiting_buyer", "needs_revision")


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- access ----------

def get_for(session: Session, user: User, req_id: uuid.UUID) -> tuple[CustomRequest, set[str]]:
    req = session.get(CustomRequest, req_id)
    roles: set[str] = set()
    if req is not None:
        if req.buyer_id == user.id:
            roles.add("buyer")
        merchant = session.get(MerchantProfile, req.merchant_id)
        tailor = session.get(TailorProfile, req.tailor_id)
        if merchant.user_id == user.id:
            roles.add("merchant")
        if tailor.user_id == user.id:
            roles.add("tailor")
        if commerce_svc.order_roles_admin(session, user):
            roles.add("admin")
    if req is None or not roles:
        raise NotFound("Custom request not found")
    return req, roles


# ---------- readiness ----------

def assert_ready(session: Session, cust: Customization) -> MaterialEstimate:
    rev = cust_svc.get_revision(session, cust, cust.current_revision)
    if rev.open_clarifications:
        raise AppValidationError("Selesaikan klarifikasi desain yang masih terbuka",
                                 field="customization")
    mset = session.get(MeasurementSet, cust.measurement_set_id) if cust.measurement_set_id else None
    if mset is None or mset.status != "confirmed":
        raise AppValidationError("Ukuran badan harus dikonfirmasi terlebih dahulu",
                                 field="measurements")
    est = material_svc.current_estimate(session, cust)
    if est is None or material_svc.stale_reasons(session, cust, est):
        raise AppValidationError("Estimasi kain belum ada atau sudah usang; hitung ulang",
                                 field="material_estimate")
    if not est.result.get("fits"):
        raise AppValidationError("Kain tidak cukup lebar untuk desain ini", field="material_estimate")
    if not est.result.get("stock_ok"):
        raise InsufficientStock("Stok kain tidak mencukupi untuk kebutuhan desain ini")
    return est


def _address(session: Session, user: User, address_id: uuid.UUID) -> dict:
    stored = session.get(DeliveryAddress, address_id)
    if stored is None or stored.user_id != user.id:
        raise NotFound("Address not found")
    return {**commerce_svc.address_out(stored), "id": str(stored.id)}


def _invalidate(session: Session, req: CustomRequest) -> None:
    """A changed request makes earlier validations, specs and quotes unusable."""
    session.execute(update(MerchantConfirmation).where(
        MerchantConfirmation.request_id == req.id, MerchantConfirmation.valid).values(valid=False))
    session.execute(update(ProductionSpec).where(
        ProductionSpec.request_id == req.id, ProductionSpec.status == "issued")
        .values(status="superseded"))
    session.execute(update(Quote).where(Quote.request_id == req.id, Quote.status == "issued")
                    .values(status="superseded"))


# ---------- buyer: create / edit / submit ----------

def create_request(session: Session, buyer: User, customization_id: uuid.UUID, tailor_id: uuid.UUID,
                   address_id: uuid.UUID) -> CustomRequest:
    cust = cust_svc.owned_customization(session, buyer, customization_id)
    listing = listings_svc.public_listing(session, cust.listing_id)
    if session.scalar(select(CustomRequest.id).where(
            CustomRequest.customization_id == cust.id, CustomRequest.status.in_(OPEN_STATES))):
        raise AppValidationError("Desain ini sudah punya permintaan yang masih berjalan",
                                 field="customization_id")
    assert_ready(session, cust)
    address = _address(session, buyer, address_id)
    tailor = matching.assert_eligible(session, cust, tailor_id, address)
    req = CustomRequest(buyer_id=buyer.id, customization_id=cust.id, listing_id=listing.id,
                        merchant_id=listing.merchant_id, tailor_id=tailor.id, address=address)
    session.add(req)
    session.flush()
    audit.record(session, actor=buyer, action="custom_request.created",
                 target_type="custom_request", target_id=req.id)
    return req


def update_request(session: Session, buyer: User, req: CustomRequest, *,
                   tailor_id: uuid.UUID | None, address_id: uuid.UUID | None) -> CustomRequest:
    if req.status not in ("draft", "needs_revision"):
        raise InvalidTransition(f"Request is {req.status}; it can no longer be edited")
    cust = session.get(Customization, req.customization_id)
    address = _address(session, buyer, address_id) if address_id else req.address
    new_tailor = tailor_id or req.tailor_id
    matching.assert_eligible(session, cust, new_tailor, address)
    if new_tailor != req.tailor_id:
        _invalidate(session, req)  # switching tailor voids the earlier validation and quote
    req.tailor_id, req.address = new_tailor, address
    session.flush()
    audit.record(session, actor=buyer, action="custom_request.updated",
                 target_type="custom_request", target_id=req.id)
    return req


def _design_preview_file(session: Session, cust: Customization) -> str | None:
    """The newest finished product preview of the submitted design revision, shared with the tailor
    as a visual reference. On-body try-ons are never shared: they are drawn on the buyer's photo."""
    preview = session.scalar(select(Preview).where(
        Preview.customization_id == cust.id, Preview.design_revision == cust.current_revision,
        Preview.kind == "product", Preview.file_id.is_not(None),
        Preview.status.in_(("completed", "completed_with_warnings")))
        .order_by(Preview.created_at.desc()).limit(1))
    return str(preview.file_id) if preview else None


def _design_preview_out(session: Session, file_id: str | None) -> dict | None:
    stored = session.get(File, uuid.UUID(file_id)) if file_id else None
    if stored is None or stored.deleted_at is not None:
        return None
    return {"url": f"/api/v1/files/{stored.id}?token={make_token(stored.id)}", "label": PREVIEW_LABEL}


def submit_request(session: Session, buyer: User, req: CustomRequest) -> CustomRequest:
    if req.status not in ("draft", "needs_revision"):
        raise InvalidTransition(f"Request is {req.status}")
    cust = session.get(Customization, req.customization_id)
    listings_svc.public_listing(session, cust.listing_id)
    est = assert_ready(session, cust)
    matching.assert_eligible(session, cust, req.tailor_id, req.address)
    rev = cust_svc.get_revision(session, cust, cust.current_revision)
    mset = session.get(MeasurementSet, cust.measurement_set_id)
    listing = session.get(FabricListing, cust.listing_id)
    values = {v.key: float(v.value_cm) for v in session.scalars(
        select(MeasurementValue).where(MeasurementValue.set_id == mset.id))
        if v.value_cm is not None}
    _invalidate(session, req)
    req.revision += 1
    req.snapshot = {
        "design_revision": cust.current_revision, "state": rev.state,
        "template": {"code": cust.template_code, "version_id": str(cust.template_version_id)},
        "measurement_set_id": str(mset.id), "measurement_revision": mset.revision,
        "measurements_cm": values, "estimate": est.result, "estimate_id": str(est.id),
        "design_preview_file_id": _design_preview_file(session, cust),
        "listing": {"id": str(listing.id), "title": listing.title, "price_idr": listing.price_idr,
                    "selling_unit": listing.selling_unit, "revision": listing.revision,
                    "material": listing.material},
    }
    req.status, req.reject_reason, req.submitted_at = "submitted", None, _now()
    session.flush()
    audit.record(session, actor=buyer, action="custom_request.submitted",
                 target_type="custom_request", target_id=req.id, metadata={"revision": req.revision})
    return req


def withdraw_request(session: Session, buyer: User, req: CustomRequest) -> CustomRequest:
    if req.status in ("converted_to_order", "withdrawn", "rejected"):
        raise InvalidTransition(f"Request is already {req.status}")
    _invalidate(session, req)
    req.status = "withdrawn"
    session.flush()
    audit.record(session, actor=buyer, action="custom_request.withdrawn",
                 target_type="custom_request", target_id=req.id)
    return req


# ---------- merchant validation ----------

def _merchant_of(session: Session, user: User, req: CustomRequest) -> MerchantProfile:
    merchant = active_merchant(session, user)
    if merchant.id != req.merchant_id:
        raise NotFound("Custom request not found")
    return merchant


def merchant_decide(session: Session, user: User, req: CustomRequest, decision: str,
                    reason: str | None) -> MerchantConfirmation:
    _merchant_of(session, user, req)
    if req.status not in ("submitted", "validating"):
        raise InvalidTransition(f"Request is {req.status}")
    if decision == "reject":
        if not reason:
            raise AppValidationError("A reason is required", field="reason")
        confirmation = MerchantConfirmation(request_id=req.id, request_revision=req.revision,
                                            decision="rejected", reason=reason, valid=False,
                                            created_by=user.id)
        req.status, req.reject_reason = "needs_revision", f"Merchant: {reason}"
    else:
        listing = listings_svc.public_listing(session, req.listing_id)
        qty = Decimal(req.snapshot["estimate"]["purchase_quantity"])
        if not commerce_svc.can_fulfill(session, listing, qty):
            raise InsufficientStock("Stok saat ini tidak mencukupi untuk permintaan ini")
        session.execute(update(MerchantConfirmation).where(
            MerchantConfirmation.request_id == req.id, MerchantConfirmation.valid)
            .values(valid=False))
        confirmation = MerchantConfirmation(
            request_id=req.id, request_revision=req.revision, decision="confirmed",
            confirmed_price_idr=listing.price_idr, confirmed_quantity=qty,
            dispatch_days=listing.dispatch_days, reason=reason, created_by=user.id)
        req.status = "validating"
    session.add(confirmation)
    session.flush()
    audit.record(session, actor=user, action=f"custom_request.merchant_{confirmation.decision}",
                 target_type="custom_request", target_id=req.id)
    return confirmation


# ---------- tailor validation ----------

def _tailor_of(session: Session, user: User, req: CustomRequest) -> TailorProfile:
    tailor = active_tailor(session, user)
    if tailor.id != req.tailor_id:
        raise NotFound("Custom request not found")
    return tailor


def tailor_decide(session: Session, user: User, req: CustomRequest, action: str,
                  reason: str) -> CustomRequest:
    _tailor_of(session, user, req)
    if req.status not in ("submitted", "validating", "ready_for_quote", "awaiting_buyer"):
        raise InvalidTransition(f"Request is {req.status}")
    _invalidate(session, req)
    if action == "reject":
        req.status = "rejected"
    else:
        req.status = "needs_revision"
    req.reject_reason = f"Tailor: {reason}"
    session.flush()
    audit.record(session, actor=user, action=f"custom_request.tailor_{action}",
                 target_type="custom_request", target_id=req.id, metadata={"reason": reason})
    return req


def _valid_confirmation(session: Session, req: CustomRequest) -> MerchantConfirmation:
    confirmation = session.scalar(select(MerchantConfirmation).where(
        MerchantConfirmation.request_id == req.id, MerchantConfirmation.valid,
        MerchantConfirmation.decision == "confirmed",
        MerchantConfirmation.request_revision == req.revision)
        .order_by(MerchantConfirmation.created_at.desc()).limit(1))
    if confirmation is None:
        raise AppValidationError("Konfirmasi stok/harga merchant diperlukan lebih dulu",
                                 field="merchant_confirmation")
    return confirmation


def issue_spec(session: Session, user: User, req: CustomRequest, data: dict) -> ProductionSpec:
    tailor = _tailor_of(session, user, req)
    if req.status not in ("submitted", "validating", "ready_for_quote", "awaiting_buyer"):
        raise InvalidTransition(f"Request is {req.status}")
    confirmation = _valid_confirmation(session, req)
    listing = session.get(FabricListing, req.listing_id)
    qty = Decimal(str(data["fabric_purchase_quantity"]))
    validate_quantity(listing, qty)
    if qty > confirmation.confirmed_quantity:
        raise AppValidationError("Kuantitas melebihi yang dikonfirmasi merchant; minta konfirmasi "
                                 "ulang", field="fabric_purchase_quantity")
    if not data["finished_dimensions"]:
        raise AppValidationError("Dimensi baju jadi wajib diisi", field="finished_dimensions")
    cap = session.scalar(select(TailorCapability).where(
        TailorCapability.tailor_id == tailor.id,
        TailorCapability.template_code == req.snapshot["template"]["code"]))
    if cap is None:
        raise AppValidationError("Kapabilitas tailor untuk template ini tidak ditemukan",
                                 field="tailor_id")
    estimate = req.snapshot["estimate"]
    previous = session.scalar(select(ProductionSpec.revision).where(
        ProductionSpec.request_id == req.id).order_by(ProductionSpec.revision.desc()).limit(1)) or 0
    session.execute(update(ProductionSpec).where(
        ProductionSpec.request_id == req.id, ProductionSpec.status == "issued")
        .values(status="superseded"))
    session.execute(update(Quote).where(Quote.request_id == req.id, Quote.status == "issued")
                    .values(status="superseded"))  # a new spec voids any open quote
    spec = {
        "template": req.snapshot["template"], "design_revision": req.snapshot["design_revision"],
        "design_state": req.snapshot["state"], "measurements_cm": req.snapshot["measurements_cm"],
        "finished_dimensions_cm": data["finished_dimensions"],
        "fabric": {"selling_unit": listing.selling_unit, "purchase_quantity": str(qty),
                   "requested_quantity": estimate.get("purchase_quantity"),
                   "required_continuous_cut_m": estimate.get("required_continuous_cut_m"),
                   "surplus_handling": data["surplus_handling"],
                   "surplus_note": "Sisa kain milik pembeli dan dikirim kembali bersama baju jadi."
                   if data["surplus_handling"] == "returned_with_garment"
                   else "Penanganan sisa kain disepakati tertulis dengan pembeli."},
        "extra_materials": data["extra_materials"], "surcharges": data["surcharges"],
        "lead_time_days": data["lead_time_days"], "motif_notes": data.get("motif_notes"),
        "change_from_request": {
            "fabric_quantity_changed": str(qty) != str(estimate.get("purchase_quantity"))},
        "visual_reference_note": "Pratinjau hanya referensi visual; spesifikasi tertulis ini mengikat.",
        "rate_version": cap.rate_version,
    }
    row = ProductionSpec(request_id=req.id, request_revision=req.revision, tailor_id=tailor.id,
                         revision=previous + 1, spec=spec)
    session.add(row)
    req.status = "ready_for_quote"
    session.flush()
    audit.record(session, actor=user, action="custom_request.spec_issued",
                 target_type="custom_request", target_id=req.id, metadata={"spec_revision": row.revision})
    return row


def issue_quote(session: Session, user: User, req: CustomRequest, spec_id: uuid.UUID,
                expires_in_hours: int) -> Quote:
    tailor = _tailor_of(session, user, req)
    if req.status not in ("ready_for_quote", "awaiting_buyer"):
        raise InvalidTransition(f"Request is {req.status}")
    spec_row = session.get(ProductionSpec, spec_id)
    if (spec_row is None or spec_row.request_id != req.id or spec_row.status != "issued"
            or spec_row.request_revision != req.revision):
        raise AppValidationError("Spesifikasi produksi tidak berlaku", field="spec_id")
    confirmation = _valid_confirmation(session, req)
    listing = session.get(FabricListing, req.listing_id)
    merchant = session.get(MerchantProfile, req.merchant_id)
    spec = spec_row.spec
    cap = session.scalar(select(TailorCapability).where(
        TailorCapability.tailor_id == tailor.id,
        TailorCapability.template_code == spec["template"]["code"]))
    qty = Decimal(spec["fabric"]["purchase_quantity"])
    unit = "m" if listing.selling_unit == "meter" else "pcs"
    lines = [("fabric", f"Kain {listing.title} ({qty} {unit})",
              line_subtotal(confirmation.confirmed_price_idr, qty), "merchant"),
             ("tailoring_base", f"Ongkos jahit dasar {spec['template']['code']}",
              cap.base_rate_idr, "tailor")]
    lines += [("surcharge", s["description"], s["amount_idr"], "tailor") for s in spec["surcharges"]]
    lines += [("extra_material", m["name"], m["price_idr"], m["provider"])
              for m in spec["extra_materials"]]
    lines.append(("shipping_leg_1", "Ongkir kain merchant → tailor (simulasi)",
                  shipping_estimate(merchant.city, merchant.province, tailor.city, tailor.province),
                  "platform"))
    lines.append(("shipping_leg_2", "Ongkir baju jadi tailor → pembeli (simulasi)",
                  shipping_estimate(tailor.city, tailor.province, req.address["city"],
                                    req.address["province"]), "platform"))
    if settings.buyer_service_fee_idr:
        lines.append(("service_fee", "Biaya layanan platform", settings.buyer_service_fee_idr,
                      "platform"))
    previous = session.scalar(select(Quote.revision).where(Quote.request_id == req.id)
                              .order_by(Quote.revision.desc()).limit(1)) or 0
    session.execute(update(Quote).where(Quote.request_id == req.id, Quote.status == "issued")
                    .values(status="superseded"))
    quote = Quote(
        request_id=req.id, spec_id=spec_row.id, merchant_confirmation_id=confirmation.id,
        request_revision=req.revision, revision=previous + 1,
        total_idr=sum(amount for _, _, amount, _ in lines),
        design_revision=req.snapshot["design_revision"],
        measurement_set_id=uuid.UUID(req.snapshot["measurement_set_id"]),
        measurement_revision=req.snapshot["measurement_revision"],
        commission={"merchant_fabric_bps": commerce_svc.commission_bps(session, "merchant_fabric"),
                    "tailoring_bps": commerce_svc.commission_bps(session, "tailoring"),
                    "rate_version": cap.rate_version},
        expires_at=_now() + timedelta(hours=expires_in_hours))
    session.add(quote)
    session.flush()
    for i, (kind, description, amount, owner) in enumerate(lines):
        session.add(QuoteLine(quote_id=quote.id, kind=kind, description=description[:300],
                              amount_idr=amount, owner=owner, sort_order=i))
    req.status = "awaiting_buyer"
    session.flush()
    audit.record(session, actor=user, action="quote.issued", target_type="quote",
                 target_id=quote.id, metadata={"total_idr": quote.total_idr, "revision": quote.revision})
    return quote


# ---------- views ----------

def quote_lines(session: Session, quote: Quote) -> list[QuoteLine]:
    return list(session.scalars(select(QuoteLine).where(QuoteLine.quote_id == quote.id)
                                .order_by(QuoteLine.sort_order)))


def effective_quote_status(quote: Quote) -> str:
    if quote.status == "issued" and quote.expires_at <= _now():
        return "expired"
    return quote.status


def quote_out(session: Session, quote: Quote) -> dict:
    req = session.get(CustomRequest, quote.request_id)
    spec = session.get(ProductionSpec, quote.spec_id).spec
    cust = session.get(Customization, req.customization_id)
    mset = session.get(MeasurementSet, cust.measurement_set_id) if cust.measurement_set_id else None
    stale = []
    if cust.current_revision != quote.design_revision:
        stale.append("design_revision_changed")
    if mset is None or mset.id != quote.measurement_set_id or mset.revision != quote.measurement_revision:
        stale.append("measurements_changed")
    status = effective_quote_status(quote)
    est = req.snapshot["estimate"]
    return {
        "id": quote.id, "request_id": quote.request_id, "revision": quote.revision,
        "status": status, "total_idr": quote.total_idr, "expires_at": quote.expires_at,
        "lines": [{"kind": ln.kind, "description": ln.description, "amount_idr": ln.amount_idr,
                   "owner": ln.owner} for ln in quote_lines(session, quote)],
        "specification": spec, "stale_reasons": stale,
        "acceptable": status == "issued" and not stale and req.revision == quote.request_revision,
        "changes_from_request": {
            "fabric_quantity_requested": est.get("purchase_quantity"),
            "fabric_quantity_in_quote": spec["fabric"]["purchase_quantity"],
            "lead_time_days": spec["lead_time_days"]},
        "surplus_fabric": spec["fabric"]["surplus_note"],
        "simulation_notice": commerce_svc.SIMULATION_NOTICE,
    }


def request_out(session: Session, req: CustomRequest, roles: set[str]) -> dict:
    snap = req.snapshot or {}
    out = {"id": req.id, "status": req.status, "revision": req.revision,
           "customization_id": req.customization_id, "listing_id": req.listing_id,
           "merchant_id": req.merchant_id, "tailor_id": req.tailor_id,
           "reject_reason": req.reject_reason, "submitted_at": req.submitted_at}
    estimate = snap.get("estimate", {})
    if roles & {"buyer", "tailor", "admin"}:
        out.update(address=req.address, design_state=snap.get("state"),
                   measurements_cm=snap.get("measurements_cm"), estimate=estimate,
                   template=snap.get("template"),
                   design_preview=_design_preview_out(session, snap.get("design_preview_file_id")))
    else:  # merchants get fulfilment details only, never body or design data
        out.update(requested_quantity=estimate.get("purchase_quantity"),
                   required_continuous_cut_m=estimate.get("required_continuous_cut_m"),
                   selling_unit=estimate.get("selling_unit"))
    return out


def not_participant(roles: set[str], allowed: set[str]) -> None:
    if not roles & allowed:
        raise Forbidden()
