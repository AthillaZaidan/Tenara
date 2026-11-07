import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, Forbidden, NotFound
from app.models import (
    File,
    MerchantProfile,
    PartnerApplication,
    PartnerReview,
    RoleAssignment,
    TailorCapability,
    TailorProfile,
    User,
)
from app.schemas.partner import MerchantData, TailorData
from app.services import audit
from app.services.signing import make_token

OPEN_STATUSES = ("draft", "submitted", "under_review", "needs_information")
DATA_MODELS = {"merchant": MerchantData, "tailor": TailorData}


def _validate_data(app_type: str, data: dict) -> dict:
    try:
        return DATA_MODELS[app_type](**data).model_dump(mode="json")
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first["loc"]) or "data"
        raise AppValidationError(first["msg"], field=f"data.{field}") from None


def _role(session: Session, user_id: uuid.UUID, role: str) -> RoleAssignment | None:
    return session.scalar(select(RoleAssignment).where(
        RoleAssignment.user_id == user_id, RoleAssignment.role == role))


def _profile_model(app_type: str):
    return MerchantProfile if app_type == "merchant" else TailorProfile


# ---------- applicant side ----------

def create_application(session: Session, user: User, app_type: str, data: dict) -> PartnerApplication:
    clean = _validate_data(app_type, data)
    role = _role(session, user.id, app_type)
    if role is not None and role.status in ("active", "suspended"):
        raise AppValidationError(f"You already are a {app_type} partner", field="type")
    open_app = session.scalar(select(PartnerApplication.id).where(
        PartnerApplication.applicant_id == user.id, PartnerApplication.type == app_type,
        PartnerApplication.status.in_(OPEN_STATUSES)))
    if open_app:
        raise AppValidationError("An application of this type is already open", field="type")
    app = PartnerApplication(applicant_id=user.id, type=app_type, data=clean)
    session.add(app)
    session.flush()
    audit.record(session, actor=user, action="partner.application_created",
                 target_type="partner_application", target_id=app.id, metadata={"type": app_type})
    return app


def get_own_application(session: Session, user: User, app_id: uuid.UUID) -> PartnerApplication:
    app = session.get(PartnerApplication, app_id)
    if app is None or app.applicant_id != user.id:
        raise NotFound("Application not found")
    return app


def update_application(session: Session, user: User, app: PartnerApplication,
                       data: dict) -> PartnerApplication:
    if app.status not in ("draft", "needs_information"):
        raise AppValidationError("This application can no longer be edited", field="status")
    app.data = _validate_data(app.type, data)
    session.flush()
    return app


def submit_application(session: Session, user: User, app: PartnerApplication) -> PartnerApplication:
    if app.status not in ("draft", "needs_information"):
        raise AppValidationError("Only draft applications can be submitted", field="status")
    evidence = [uuid.UUID(x) for x in app.data.get("evidence_file_ids", [])]
    if not evidence:
        raise AppValidationError("Verification evidence is required", field="data.evidence_file_ids")
    for file_id in evidence:
        f = session.get(File, file_id)
        if f is None or f.owner_id != user.id or f.deleted_at is not None:
            raise AppValidationError("Evidence files must be your own uploads",
                                     field="data.evidence_file_ids")
    app.status = "submitted"
    app.submitted_at = datetime.now(UTC)
    if _role(session, user.id, app.type) is None:
        session.add(RoleAssignment(user_id=user.id, role=app.type, status="pending"))
    session.flush()
    audit.record(session, actor=user, action="partner.application_submitted",
                 target_type="partner_application", target_id=app.id)
    return app


# ---------- reviewer side ----------

def evidence_links(session: Session, admin: User, app: PartnerApplication) -> list[dict]:
    links = []
    for raw in app.data.get("evidence_file_ids", []):
        file_id = uuid.UUID(raw)
        file = session.get(File, file_id)
        if file is not None and file.deleted_at is None:
            links.append({"file_id": file_id, "content_type": file.content_type,
                          "url": f"/api/v1/files/{file_id}?token={make_token(file_id)}"})
    audit.record(session, actor=admin, action="partner.evidence_viewed",
                 target_type="partner_application", target_id=app.id)
    return links


def _activate(session: Session, admin: User, app: PartnerApplication) -> None:
    model = _profile_model(app.type)
    data = app.data
    profile = session.scalar(select(model).where(model.user_id == app.applicant_id))
    fields = {"shop_name": data["shop_name"], "city": data["city"], "province": data["province"],
              "contact_phone": data.get("contact_phone")}
    if app.type == "merchant":
        fields["description"] = data.get("description", "")
    else:
        fields.update(bio=data.get("description", ""), service_area=data.get("service_area", []),
                      experience_years=data.get("experience_years"))
    if profile is None:
        session.add(model(user_id=app.applicant_id, **fields))
    else:
        for key, value in fields.items():
            setattr(profile, key, value)
        profile.status = "active"
    role = _role(session, app.applicant_id, app.type)
    now = datetime.now(UTC)
    if role is None:
        session.add(RoleAssignment(user_id=app.applicant_id, role=app.type, status="active",
                                   decided_by=admin.id, decided_at=now))
    else:
        role.status, role.decided_by, role.decided_at = "active", admin.id, now


def review_application(session: Session, admin: User, app: PartnerApplication, action: str,
                       reason: str | None) -> PartnerApplication:
    allowed = {"start_review": ("submitted",), "approve": ("submitted", "under_review"),
               "reject": ("submitted", "under_review"),
               "request_information": ("submitted", "under_review")}
    if app.status not in allowed[action]:
        raise AppValidationError(f"Cannot {action} an application that is {app.status}",
                                 field="status")
    if action in ("reject", "request_information") and not reason:
        raise AppValidationError("A reason is required", field="reason")
    app.status = {"start_review": "under_review", "approve": "approved", "reject": "rejected",
                  "request_information": "needs_information"}[action]
    if action in ("approve", "reject"):
        app.decided_at = datetime.now(UTC)
        app.decision_reason = reason
    if action == "approve":
        _activate(session, admin, app)
    elif action == "reject":
        session.execute(delete(RoleAssignment).where(
            RoleAssignment.user_id == app.applicant_id, RoleAssignment.role == app.type,
            RoleAssignment.status == "pending"))
    session.add(PartnerReview(application_id=app.id, reviewer_id=admin.id, action=action,
                              reason=reason))
    session.flush()
    audit.record(session, actor=admin, action=f"partner.{action}", target_type="partner_application",
                 target_id=app.id, metadata={"reason": reason})
    return app


def set_partner_status(session: Session, admin: User, user_id: uuid.UUID, role_name: str,
                       suspend: bool, reason: str | None) -> None:
    if suspend and not reason:
        raise AppValidationError("A reason is required to suspend a partner", field="reason")
    role = _role(session, user_id, role_name)
    profile = session.scalar(select(_profile_model(role_name)).where(
        _profile_model(role_name).user_id == user_id))
    if role is None or profile is None:
        raise NotFound("Partner not found")
    role.status = "suspended" if suspend else "active"
    role.decided_by, role.decided_at = admin.id, datetime.now(UTC)
    profile.status = "suspended" if suspend else "active"
    session.flush()
    audit.record(session, actor=admin, action="partner.suspended" if suspend else "partner.reinstated",
                 target_type="user", target_id=user_id, metadata={"role": role_name, "reason": reason})


# ---------- eligibility ----------

def active_merchant(session: Session, user: User) -> MerchantProfile:
    profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    role = _role(session, user.id, "merchant")
    if profile is None or profile.status != "active" or role is None or role.status != "active":
        raise Forbidden("An approved, active merchant account is required")
    return profile


def active_tailor(session: Session, user: User) -> TailorProfile:
    profile = session.scalar(select(TailorProfile).where(TailorProfile.user_id == user.id))
    role = _role(session, user.id, "tailor")
    if profile is None or profile.status != "active" or role is None or role.status != "active":
        raise Forbidden("An approved, active tailor account is required")
    return profile


# ---------- tailor capabilities ----------

def upsert_capability(session: Session, tailor: TailorProfile, template_code: str, *,
                      base_rate_idr: int, lead_time_days: int, weekly_capacity: int,
                      materials: list[str], supported_options: dict) -> TailorCapability:
    cap = session.scalar(select(TailorCapability).where(
        TailorCapability.tailor_id == tailor.id, TailorCapability.template_code == template_code))
    if cap is None:
        cap = TailorCapability(tailor_id=tailor.id, template_code=template_code,
                               base_rate_idr=base_rate_idr, lead_time_days=lead_time_days,
                               weekly_capacity=weekly_capacity, materials=materials,
                               supported_options=supported_options)
        session.add(cap)
    else:
        if cap.base_rate_idr != base_rate_idr:
            cap.rate_version += 1
        cap.base_rate_idr, cap.lead_time_days = base_rate_idr, lead_time_days
        cap.weekly_capacity, cap.materials = weekly_capacity, materials
        cap.supported_options = supported_options
    session.flush()
    return cap


def capabilities(session: Session, tailor_id: uuid.UUID) -> list[TailorCapability]:
    return list(session.scalars(select(TailorCapability)
                                .where(TailorCapability.tailor_id == tailor_id)
                                .order_by(TailorCapability.template_code)))


def capability_out(cap: TailorCapability) -> dict:
    return {"template_code": cap.template_code, "base_rate_idr": cap.base_rate_idr,
            "lead_time_days": cap.lead_time_days, "weekly_capacity": cap.weekly_capacity,
            "materials": list(cap.materials), "supported_options": cap.supported_options,
            "rate_version": cap.rate_version}


def application_out(app: PartnerApplication) -> dict:
    return {"id": app.id, "type": app.type, "status": app.status, "data": app.data,
            "submitted_at": app.submitted_at, "decided_at": app.decided_at,
            "decision_reason": app.decision_reason, "applicant_id": app.applicant_id}


def merchant_public(p: MerchantProfile) -> dict:
    return {"id": p.id, "shop_name": p.shop_name, "description": p.description, "city": p.city,
            "province": p.province, "verified": True,
            "verification_note": ("Mitra terverifikasi platform. Ini bukan sertifikasi keaslian "
                                  "atau asal-usul kain tertentu.")}


def tailor_public(session: Session, p: TailorProfile) -> dict:
    return {"id": p.id, "shop_name": p.shop_name, "bio": p.bio, "city": p.city,
            "province": p.province, "service_area": list(p.service_area),
            "experience_years": p.experience_years, "verified": True,
            "capabilities": [capability_out(c) for c in capabilities(session, p.id)]}
