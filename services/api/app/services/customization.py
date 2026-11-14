import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, NotFound, StaleRevision
from app.core.revision import check_revision
from app.ml.text.prompt_interpreter import InterpretationFailed, get_interpreters
from app.models import (
    Customization,
    DesignRevision,
    FabricListing,
    Job,
    MeasurementSet,
    MeasurementValue,
    Preview,
    PromptRequest,
    TemplateVersion,
    User,
)
from app.services import audit, jobs
from app.services import listings as listings_svc
from app.services import templates as templates_svc
from app.services.signing import make_token
from app.services.template_defs import defaults

LIVE_PREVIEW_STATES = ("queued", "processing", "completed", "completed_with_warnings")

jobs.register_revision_resolver(
    "customization",
    lambda session, subject_id: session.get(Customization, subject_id).current_revision,
)


def definition_of(session: Session, cust: Customization) -> dict:
    return session.get(TemplateVersion, cust.template_version_id).definition


def owned_customization(session: Session, user: User, cust_id: uuid.UUID) -> Customization:
    cust = session.get(Customization, cust_id)
    if cust is None or cust.buyer_id != user.id:
        raise NotFound("Customization not found")
    return cust


def get_revision(session: Session, cust: Customization, revision: int) -> DesignRevision:
    row = session.scalar(select(DesignRevision).where(
        DesignRevision.customization_id == cust.id, DesignRevision.revision == revision))
    if row is None:
        raise NotFound("Design revision not found")
    return row


def create_customization(session: Session, buyer: User, listing_id: uuid.UUID,
                         template_code: str) -> Customization:
    listing = listings_svc.public_listing(session, listing_id)
    version = templates_svc.latest_version(session, template_code)
    if version is None:
        raise NotFound("Template not found")
    compat = next(c for c in templates_svc.compatibility(session, listing)
                  if c["code"] == template_code)
    if not compat["compatible"]:
        raise AppValidationError("; ".join(compat["reasons"]), field="template_code")
    cust = Customization(buyer_id=buyer.id, listing_id=listing.id, entry_id=listing.entry_id,
                         template_code=template_code, template_version_id=version.id,
                         current_revision=1)
    session.add(cust)
    session.flush()
    session.add(DesignRevision(customization_id=cust.id, revision=1,
                               state=defaults(version.definition), source="initial",
                               created_by=buyer.id))
    session.flush()
    audit.record(session, actor=buyer, action="customization.created",
                 target_type="customization", target_id=cust.id,
                 metadata={"template": template_code, "listing_id": str(listing.id)})
    return cust


# ---------- prompt -> proposal ----------

def _validate_candidates(defn: dict, listing: FabricListing, state: dict, raw: dict) -> dict:
    changes, unsupported, clarifications = [], [], []
    for cand in raw.get("changes", []):
        field = cand.get("field")
        try:
            value = templates_svc.validate_value(defn, field, cand.get("value"), listing)
        except ValueError as exc:
            spec = defn["options"].get(field, {})
            unsupported.append({"text": f"{field}={cand.get('value')}", "reason": str(exc),
                                "alternatives": spec.get("values", [])})
            continue
        if value != state.get(field):
            changes.append({"field": field, "operation": "set", "value": value,
                            "from": state.get(field), "status": "accepted"})
    for item in raw.get("unsupported", []):
        unsupported.append({"text": item.get("text", ""), "reason": item.get("reason", ""),
                            "alternatives": item.get("alternatives", [])})
    for i, clar in enumerate(raw.get("clarifications", [])):
        clarifications.append({**clar, "id": f"c{i}", "status": "ambiguous"})
    return {"changes": changes, "unsupported_requests": unsupported, "clarifications": clarifications}


def propose(session: Session, user: User, cust: Customization, expected_revision: int,
            prompt: str) -> PromptRequest:
    check_revision(expected_revision, cust.current_revision)
    listing = session.get(FabricListing, cust.listing_id)
    defn = definition_of(session, cust)
    state = get_revision(session, cust, cust.current_revision).state
    raw, used = None, None
    for interpreter in get_interpreters():
        try:
            raw, used = interpreter.interpret(prompt, defn, state), interpreter.name
            break
        except InterpretationFailed:
            continue
    body = _validate_candidates(defn, listing, state, raw or {})
    understood = bool(body["changes"] or body["clarifications"])
    proposal = {
        "base_design_revision": cust.current_revision, **body,
        "requires_buyer_confirmation": True, "requires_tailor_validation": True,
        "interpreter": used or "none",
        "fallback": None if understood else "structured_controls",
        "unapproved_note": None if understood else prompt,
    }
    session.execute(update(PromptRequest).where(
        PromptRequest.customization_id == cust.id, PromptRequest.status == "proposed")
        .values(status="superseded"))
    request = PromptRequest(customization_id=cust.id, base_revision=cust.current_revision,
                            prompt=prompt, proposal=proposal, interpreter=used or "none")
    session.add(request)
    session.flush()
    audit.record(session, actor=user, action="customization.prompt_interpreted",
                 target_type="customization", target_id=cust.id,
                 metadata={"proposal_id": str(request.id), "interpreter": used})
    return request


def proposal_out(request: PromptRequest) -> dict:
    return {"proposal_id": request.id, "status": request.status, **request.proposal}


# ---------- apply / revert ----------

def _diff(old: dict, new: dict) -> list[dict]:
    return [{"field": k, "from": old.get(k), "to": v} for k, v in new.items() if old.get(k) != v]


def _validated(defn: dict, listing: FabricListing, field: str, value, error_field: str):
    try:
        return templates_svc.validate_value(defn, field, value, listing)
    except ValueError as exc:
        raise AppValidationError(str(exc), field=error_field) from None


def apply_revision(session: Session, user: User, cust: Customization, expected_revision: int, *,
                   proposal_id: uuid.UUID | None = None, resolutions: dict | None = None,
                   changes: dict | None = None, revert_to: int | None = None) -> DesignRevision:
    if sum(x is not None for x in (proposal_id, changes, revert_to)) != 1:
        raise AppValidationError("Provide exactly one of proposal_id, changes or revert_to",
                                 field="proposal_id")
    check_revision(expected_revision, cust.current_revision)
    listing = session.get(FabricListing, cust.listing_id)
    defn = definition_of(session, cust)
    current = get_revision(session, cust, cust.current_revision)
    state = dict(current.state)
    applied: dict = {}
    carried = list(current.open_clarifications)
    open_clar: list = []
    source, prompt_text, interpretation, reverted_from, request = "manual", None, None, None, None

    if proposal_id is not None:
        request = session.get(PromptRequest, proposal_id)
        if request is None or request.customization_id != cust.id:
            raise NotFound("Proposal not found")
        if request.status != "proposed":
            raise AppValidationError(f"Proposal is already {request.status}", field="proposal_id")
        if request.base_revision != cust.current_revision:
            raise StaleRevision("The design changed after this proposal; interpret the request again")
        proposal = request.proposal
        applied = {c["field"]: c["value"] for c in proposal["changes"]}
        for clar in proposal["clarifications"]:
            choice = (resolutions or {}).get(clar["id"])
            if choice is None:
                open_clar.append(clar)
                continue
            if clar["field"] == "length":
                if choice not in clar["choices"]:
                    raise AppValidationError("Pilihan tidak valid", field=f"resolutions.{clar['id']}")
                field, value = choice, (state.get(choice, 0) or 0) + clar["direction"]
            else:
                field, value = clar["field"], choice
            applied[field] = _validated(defn, listing, field, value, f"resolutions.{clar['id']}")
        source, prompt_text, interpretation = "prompt", request.prompt, proposal
    elif changes is not None:
        for field, value in changes.items():
            applied[field] = _validated(defn, listing, field, value, f"changes.{field}")
    else:
        target = get_revision(session, cust, revert_to)
        if revert_to == cust.current_revision:
            raise AppValidationError("That already is the current revision", field="revert_to")
        applied, source, reverted_from = dict(target.state), "revert", revert_to

    new_state = {**state, **applied}
    diff = _diff(state, new_state)
    if not diff:
        raise AppValidationError("Tidak ada perubahan yang dapat diterapkan; selesaikan "
                                 "klarifikasi atau ubah nilainya", field="changes")
    still_open = [c for c in carried if c["field"] not in applied and c["field"] != "length"]
    revision = DesignRevision(
        customization_id=cust.id, revision=cust.current_revision + 1, state=new_state, changes=diff,
        source=source, prompt_text=prompt_text, interpretation=interpretation,
        open_clarifications=still_open + open_clar, reverted_from=reverted_from,
        created_by=user.id)
    session.add(revision)
    cust.current_revision = revision.revision
    session.execute(update(Preview).where(
        Preview.customization_id == cust.id, Preview.design_revision < revision.revision,
        Preview.status.in_(LIVE_PREVIEW_STATES)).values(status="stale"))
    if request is not None:
        request.status, request.resulting_revision = "applied", revision.revision
    session.flush()
    audit.record(session, actor=user, action="customization.revision_created",
                 target_type="customization", target_id=cust.id,
                 metadata={"revision": revision.revision, "source": source})
    return revision


def revision_out(rev: DesignRevision) -> dict:
    return {"revision": rev.revision, "source": rev.source, "state": rev.state,
            "changes": rev.changes, "prompt_text": rev.prompt_text,
            "open_clarifications": rev.open_clarifications, "reverted_from": rev.reverted_from,
            "created_at": rev.created_at}


# ---------- previews (rendering itself belongs to the AI worker sub-project) ----------

def request_preview(session: Session, user: User, cust: Customization) -> Preview:
    preview = Preview(customization_id=cust.id, design_revision=cust.current_revision,
                      kind="product")
    session.add(preview)
    session.flush()
    job = jobs.enqueue(session, "preview.product", user.id, {"preview_id": str(preview.id)},
                       subject_type="customization", subject_id=cust.id,
                       subject_revision=cust.current_revision)
    preview.job_id = job.id
    session.flush()
    return preview


def request_on_body_preview(session: Session, user: User, cust: Customization,
                            photo_id: uuid.UUID) -> Preview:
    preview = Preview(customization_id=cust.id, design_revision=cust.current_revision,
                      kind="on_body", body_photo_id=photo_id)
    session.add(preview)
    session.flush()
    job = jobs.enqueue(session, "preview.on_body", user.id,
                       {"preview_id": str(preview.id), "photo_id": str(photo_id)},
                       subject_type="customization", subject_id=cust.id,
                       subject_revision=cust.current_revision)
    preview.job_id = job.id
    session.flush()
    return preview


AVATAR_GENDERS = ("neutral", "female", "male")
AVATAR_LABEL = ("Perkiraan bentuk badan dari ukuran Anda dengan baju rancangan; bukan simulasi jatuhnya kain, "
                "pola potong, atau jaminan hasil akhir.")


def request_avatar_preview(session: Session, user: User, cust: Customization, mset: MeasurementSet,
                           gender: str) -> Preview:
    """The buyer's body rebuilt from a measurement set (numbers only, no photo) wearing the current design."""
    if gender not in AVATAR_GENDERS:
        raise AppValidationError(f"gender harus salah satu dari {', '.join(AVATAR_GENDERS)}", field="gender")
    if mset.height_cm is None:
        raise AppValidationError("Isi tinggi badan dulu; avatar 3D diskalakan dari tinggi badan",
                                 field="measurement_set_id")
    filled = session.scalar(select(MeasurementValue.id).where(MeasurementValue.set_id == mset.id,
                                                              MeasurementValue.value_cm.is_not(None)).limit(1))
    if filled is None:
        raise AppValidationError("Isi minimal satu ukuran badan", field="measurement_set_id")
    preview = Preview(customization_id=cust.id, design_revision=cust.current_revision, kind="avatar_3d",
                      measurement_set_id=mset.id, measurement_revision=mset.revision)
    session.add(preview)
    session.flush()
    job = jobs.enqueue(session, "preview.avatar_3d", user.id,
                       {"preview_id": str(preview.id), "gender": gender},
                       subject_type="customization", subject_id=cust.id,
                       subject_revision=cust.current_revision)
    preview.job_id = job.id
    session.flush()
    return preview


def owned_preview(session: Session, user: User, preview_id: uuid.UUID) -> Preview:
    preview = session.get(Preview, preview_id)
    cust = session.get(Customization, preview.customization_id) if preview else None
    if preview is None or cust.buyer_id != user.id:
        raise NotFound("Preview not found")
    return preview


def preview_out(session: Session, preview: Preview) -> dict:
    cust = session.get(Customization, preview.customization_id)
    job = session.get(Job, preview.job_id) if preview.job_id else None
    status, warnings = preview.status, list(preview.warnings)
    outdated = preview.design_revision != cust.current_revision
    if preview.kind == "avatar_3d":  # also stale once the measurements it was built from change
        mset = session.get(MeasurementSet, preview.measurement_set_id) if preview.measurement_set_id else None
        outdated = outdated or mset is None or mset.revision != preview.measurement_revision
    if job is not None and job.status == "failed":
        status = "failed"
        if job.error:
            warnings.append(job.error)
    elif outdated:
        status = "stale"
    elif job is not None and job.status in ("queued", "processing"):
        status = job.status  # the job is the source of truth until it has produced an image
    url = (f"/api/v1/files/{preview.file_id}?token={make_token(preview.file_id)}"
           if preview.file_id and status != "stale" else None)
    return {"id": preview.id, "kind": preview.kind, "status": status,
            "design_revision": preview.design_revision, "method": preview.method,
            "warnings": warnings, "job_id": preview.job_id, "url": url,
            "measurement_set_id": preview.measurement_set_id,
            "label": AVATAR_LABEL if preview.kind == "avatar_3d"
            else "Ilustrasi konseptual; bukan pola potong atau jaminan hasil akhir."}
