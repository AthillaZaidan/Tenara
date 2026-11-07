import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppValidationError, Forbidden, InvalidTransition, NotFound
from app.models import (
    Appeal,
    Claim,
    ClaimDecision,
    ClaimEvidence,
    ClaimResponse,
    FabricInspection,
    File,
    MerchantProfile,
    Message,
    Order,
    OrderAmendment,
    OrderEvent,
    RemedyEvent,
    SettlementEntry,
    Shipment,
    TailorProfile,
    User,
)
from app.services import audit
from app.services import chat as chat_svc
from app.services import commerce as commerce_svc
from app.services.pricing import commission
from app.services.signing import make_token

OPEN_STATUSES = ("opened", "partner_discussion", "resolution_proposed", "partner_rejected",
                 "appealed", "internal_review", "decision_issued")
EXECUTABLE_REMEDIES = ("rework", "replacement", "refund_partial", "refund_full")
REMEDY_TYPES = ("none", "explanation", "rework", "replacement", "refund_partial", "refund_full")


def _now() -> datetime:
    return datetime.now(UTC)


def has_open_claim(session, order_id: uuid.UUID) -> bool:
    return session.scalar(select(Claim.id).where(
        Claim.order_id == order_id, Claim.status.in_(OPEN_STATUSES)).limit(1)) is not None


# ---------- demo policy: claim window + partner response SLA ----------

def delivered_at(session, order_id: uuid.UUID) -> datetime | None:
    return session.scalar(select(OrderEvent.created_at).where(
        OrderEvent.order_id == order_id, OrderEvent.to_status == "delivered")
        .order_by(OrderEvent.created_at).limit(1))


def claim_window_ends(session, order_id: uuid.UUID) -> datetime | None:
    delivered = delivered_at(session, order_id)
    return delivered + timedelta(days=settings.claim_window_days) if delivered else None


def partner_due_at(session, claim: Claim) -> datetime:
    """The partner must react within the SLA after the claim opened, their last reply, or the
    buyer's last rejection of a proposal (whichever is latest)."""
    anchors = [claim.created_at]
    for r in session.scalars(select(ClaimResponse).where(ClaimResponse.claim_id == claim.id)):
        anchors.append(r.created_at)
        if r.decided_at:
            anchors.append(r.decided_at)
    return max(anchors) + timedelta(hours=settings.partner_response_sla_hours)


def partner_overdue(session, claim: Claim) -> bool:
    return claim.status in ("opened", "partner_discussion") and _now() > partner_due_at(session, claim)


# ---------- access ----------

def claim_for(session, user: User, claim_id: uuid.UUID) -> tuple[Claim, set[str]]:
    claim = session.get(Claim, claim_id)
    roles: set[str] = set()
    if claim is not None:
        if claim.buyer_id == user.id:
            roles.add("buyer")
        if claim.target_user_id == user.id:
            roles.add("target")
        appeal = session.scalar(select(Appeal).where(Appeal.claim_id == claim.id))
        if appeal is not None and appeal.reviewer_id == user.id:
            roles.add("reviewer")
    if claim is None or not roles:
        raise NotFound("Claim not found")
    return claim, roles


def _own_file(session, user: User, file_id: uuid.UUID) -> File:
    f = session.get(File, file_id)
    if f is None or f.owner_id != user.id or f.deleted_at is not None:
        raise AppValidationError("Evidence files must be your own uploads", field="evidence_file_ids")
    return f


# ---------- opening + evidence ----------

def open_claim(session, buyer: User, order_id: uuid.UUID, target: str, component: str,
               description: str, evidence_file_ids: list[uuid.UUID]) -> Claim:
    order, roles = commerce_svc.get_order_for(session, buyer, order_id)
    if "buyer" not in roles:
        raise Forbidden("Only the buyer can open a claim")
    if order.status == "cancelled":
        raise InvalidTransition("Cancelled orders cannot be claimed")
    window_end = claim_window_ends(session, order.id)
    if window_end is not None and _now() > window_end:
        raise AppValidationError(
            f"Batas waktu klaim ({settings.claim_window_days} hari setelah pengiriman diterima) "
            "sudah terlewati", field="order_id")
    if target == "tailor" and not order.tailor_id:
        raise AppValidationError("Pesanan ini tidak memiliki tailor", field="target")
    target_user = (session.get(MerchantProfile, order.merchant_id).user_id if target == "merchant"
                   else session.get(TailorProfile, order.tailor_id).user_id)
    duplicate = session.scalar(select(Claim.id).where(
        Claim.order_id == order.id, Claim.target_role == target, Claim.component == component,
        Claim.status.in_(OPEN_STATUSES)))
    if duplicate:
        raise AppValidationError("Klaim untuk komponen ini sudah terbuka", field="component")
    files = [_own_file(session, buyer, fid) for fid in evidence_file_ids]
    claim = Claim(order_id=order.id, buyer_id=buyer.id, target_role=target, target_user_id=target_user,
                  component=component, description=description)
    session.add(claim)
    session.flush()
    conv = chat_svc.create_claim_conversation(session, claim.id, order.id, buyer.id, target_user,
                                              target, buyer.id)
    claim.conversation_id = conv.id
    for f in files:
        session.add(ClaimEvidence(claim_id=claim.id, uploaded_by=buyer.id, file_id=f.id))
    session.flush()
    audit.record(session, actor=buyer, action="claim.opened", target_type="claim",
                 target_id=claim.id, metadata={"order_id": str(order.id), "target": target})
    return claim


def add_evidence(session, user: User, claim: Claim, file_id: uuid.UUID, note: str | None) -> ClaimEvidence:
    if claim.status in ("resolved", "withdrawn"):
        raise InvalidTransition(f"Claim is {claim.status}")
    f = _own_file(session, user, file_id)
    row = ClaimEvidence(claim_id=claim.id, uploaded_by=user.id, file_id=f.id, note=note)
    session.add(row)
    session.flush()
    audit.record(session, actor=user, action="claim.evidence_added", target_type="claim",
                 target_id=claim.id)
    return row


# ---------- partner side ----------

def partner_respond(session, user: User, claim: Claim, kind: str, reason: str,
                    proposal: dict | None) -> ClaimResponse:
    if claim.target_user_id != user.id:
        raise Forbidden()
    if claim.status not in ("opened", "partner_discussion", "resolution_proposed"):
        raise InvalidTransition(f"Claim is {claim.status}")
    if kind == "proposal":
        if not proposal or proposal.get("remedy_type") not in REMEDY_TYPES:
            raise AppValidationError("Proposal needs a valid remedy_type", field="proposal")
        if proposal["remedy_type"].startswith("refund") and not proposal.get("amount_idr"):
            raise AppValidationError("Refund proposals need amount_idr", field="proposal")
    response = ClaimResponse(claim_id=claim.id, responder_id=user.id, kind=kind, reason=reason,
                             proposal=proposal if kind == "proposal" else None)
    session.add(response)
    claim.status = {"discussion": "partner_discussion", "proposal": "resolution_proposed",
                    "rejection": "partner_rejected"}[kind]
    session.flush()
    audit.record(session, actor=user, action=f"claim.partner_{kind}", target_type="claim",
                 target_id=claim.id)
    return response


def buyer_decide(session, buyer: User, claim: Claim, response_id: uuid.UUID,
                 decision: str) -> Claim:
    if claim.buyer_id != buyer.id:
        raise Forbidden()
    response = session.get(ClaimResponse, response_id)
    if response is None or response.claim_id != claim.id or response.kind != "proposal":
        raise NotFound("Proposal not found")
    latest = session.scalar(select(ClaimResponse.id).where(
        ClaimResponse.claim_id == claim.id, ClaimResponse.kind == "proposal")
        .order_by(ClaimResponse.created_at.desc(), ClaimResponse.id.desc()).limit(1))
    if claim.status != "resolution_proposed" or response.buyer_decision != "pending" \
            or latest != response.id:
        raise InvalidTransition("That proposal can no longer be decided")
    response.buyer_decision = "accepted" if decision == "accept" else "rejected"
    response.decided_at = _now()
    if decision == "accept":
        claim.status, claim.resolved_at = "resolved", _now()
    else:
        claim.status = "partner_discussion"  # back to the partner; appeal needs a recorded rejection
    session.flush()
    audit.record(session, actor=buyer, action=f"claim.proposal_{response.buyer_decision}",
                 target_type="claim", target_id=claim.id)
    return claim


def withdraw(session, buyer: User, claim: Claim) -> Claim:
    if claim.buyer_id != buyer.id:
        raise Forbidden()
    if claim.status not in ("opened", "partner_discussion", "resolution_proposed",
                            "partner_rejected"):
        raise InvalidTransition(f"Claim is {claim.status}")
    claim.status = "withdrawn"
    session.flush()
    audit.record(session, actor=buyer, action="claim.withdrawn", target_type="claim",
                 target_id=claim.id)
    return claim


# ---------- appeal + internal review ----------

def appeal(session, buyer: User, claim: Claim, rejection_id: uuid.UUID, reason: str,
           evidence_ids: list[uuid.UUID]) -> Appeal:
    if claim.buyer_id != buyer.id:
        raise Forbidden()
    if claim.status != "partner_rejected":
        raise InvalidTransition("Appeals need a recorded partner rejection")
    latest = session.scalar(select(ClaimResponse).where(
        ClaimResponse.claim_id == claim.id, ClaimResponse.kind == "rejection")
        .order_by(ClaimResponse.created_at.desc(), ClaimResponse.id.desc()).limit(1))
    if latest is None or latest.id != rejection_id:
        raise AppValidationError("Rejection tidak valid atau bukan yang terbaru",
                                 field="partner_rejection_id")
    for eid in evidence_ids:
        row = session.get(ClaimEvidence, eid)
        if row is None or row.claim_id != claim.id:
            raise AppValidationError("Evidence does not belong to this claim", field="evidence_ids")
    row = Appeal(claim_id=claim.id, rejection_id=rejection_id, basis="rejection", buyer_id=buyer.id,
                 reason=reason, evidence_ids=[str(e) for e in evidence_ids])
    session.add(row)
    claim.status = "appealed"
    session.flush()
    audit.record(session, actor=buyer, action="claim.appealed", target_type="claim",
                 target_id=claim.id, metadata={"appeal_id": str(row.id)})
    return row


def escalate_no_response(session, buyer: User, claim: Claim, reason: str) -> Appeal:
    """Explicit rule: only after the partner missed the SLA may the buyer ask for internal review.
    Silence is never treated as a partner rejection; the appeal records its own basis."""
    if claim.buyer_id != buyer.id:
        raise Forbidden()
    if claim.status not in ("opened", "partner_discussion"):
        raise InvalidTransition(f"Claim is {claim.status}")
    if not partner_overdue(session, claim):
        raise InvalidTransition("Mitra masih dalam batas waktu respons "
                                f"({settings.partner_response_sla_hours} jam)")
    row = Appeal(claim_id=claim.id, rejection_id=None, basis="no_response", buyer_id=buyer.id,
                 reason=reason, evidence_ids=[])
    session.add(row)
    claim.status = "appealed"
    session.flush()
    audit.record(session, actor=buyer, action="claim.escalated_no_response", target_type="claim",
                 target_id=claim.id, metadata={"appeal_id": str(row.id)})
    return row


def get_appeal(session, appeal_id: uuid.UUID) -> Appeal:
    row = session.get(Appeal, appeal_id)
    if row is None:
        raise NotFound("Appeal not found")
    return row


def start_review(session, admin: User, row: Appeal) -> Appeal:
    claim = session.get(Claim, row.claim_id)
    if admin.id in (claim.buyer_id, claim.target_user_id):
        raise Forbidden("A party to the claim cannot review it")
    if row.status != "pending":
        raise InvalidTransition(f"Appeal is {row.status}")
    row.status, row.reviewer_id = "under_review", admin.id
    claim.status = "internal_review"
    chat_svc.add_member(session, claim.conversation_id, admin.id, "reviewer")
    session.flush()
    audit.record(session, actor=admin, action="claim.review_started", target_type="claim",
                 target_id=claim.id, metadata={"appeal_id": str(row.id)})
    return row


def request_evidence(session, admin: User, row: Appeal, message: str) -> Message:
    claim = session.get(Claim, row.claim_id)
    if row.reviewer_id != admin.id or row.status != "under_review":
        raise Forbidden()
    conv = session.get(chat_svc.Conversation, claim.conversation_id)
    sent = chat_svc.send_message(session, admin, conv, f"[Permintaan bukti reviewer] {message}")
    audit.record(session, actor=admin, action="claim.evidence_requested", target_type="claim",
                 target_id=claim.id)
    return sent


def decide(session, admin: User, row: Appeal, *, outcome: str, remedy_type: str,
           amount_idr: int | None, reasoning: str) -> ClaimDecision:
    claim = session.get(Claim, row.claim_id)
    if row.reviewer_id != admin.id or row.status != "under_review":
        raise Forbidden("Only the assigned reviewer can decide an appeal under review")
    if outcome == "upheld_rejection" and remedy_type != "none":
        raise AppValidationError("Upholding the rejection means no remedy", field="remedy_type")
    if outcome != "upheld_rejection" and remedy_type == "none":
        raise AppValidationError("Overturning needs a remedy", field="remedy_type")
    order = session.get(Order, claim.order_id)
    if remedy_type.startswith("refund"):
        if remedy_type == "refund_full" and not amount_idr:
            amount_idr = order.total_idr
        if not amount_idr or amount_idr <= 0 or amount_idr > order.total_idr:
            raise AppValidationError("Refund amount must be within the order total", field="amount_idr")
    requires_execution = remedy_type in EXECUTABLE_REMEDIES
    decision = ClaimDecision(appeal_id=row.id, claim_id=claim.id, reviewer_id=admin.id,
                             outcome=outcome, remedy_type=remedy_type, amount_idr=amount_idr,
                             reasoning=reasoning, requires_execution=requires_execution)
    session.add(decision)
    row.status = "decided"
    claim.status = "decision_issued"
    if not requires_execution:
        claim.status, claim.resolved_at = "resolved", _now()
    session.flush()
    audit.record(session, actor=admin, action="claim.decided", target_type="claim",
                 target_id=claim.id, metadata={"outcome": outcome, "remedy_type": remedy_type,
                                               "amount_idr": amount_idr})
    return decision


def execute_remedy(session, actor: User, claim: Claim, action: str, amount_idr: int | None,
                   note: str | None, is_admin: bool) -> RemedyEvent:
    """Record (simulated) execution. The decision itself is never modified."""
    decision = session.scalar(select(ClaimDecision).where(ClaimDecision.claim_id == claim.id))
    accepted = session.scalar(select(ClaimResponse).where(
        ClaimResponse.claim_id == claim.id, ClaimResponse.kind == "proposal",
        ClaimResponse.buyer_decision == "accepted"))
    if decision is not None and decision.requires_execution:
        authorised = is_admin
        ordered_type, ordered_amount = decision.remedy_type, decision.amount_idr
    elif accepted is not None and accepted.proposal["remedy_type"] in EXECUTABLE_REMEDIES:
        authorised = is_admin or claim.target_user_id == actor.id
        ordered_type, ordered_amount = accepted.proposal["remedy_type"], accepted.proposal.get("amount_idr")
    else:
        raise InvalidTransition("No remedy is waiting to be executed")
    if not authorised:
        raise Forbidden()
    if action != ordered_type:
        raise AppValidationError(f"Ordered remedy is '{ordered_type}'", field="action")
    done = list(session.scalars(select(RemedyEvent).where(
        RemedyEvent.claim_id == claim.id, RemedyEvent.action == action)))
    if action.startswith("refund"):
        remaining = (ordered_amount or 0) - sum(e.amount_idr or 0 for e in done)
        amount = amount_idr or remaining
        if remaining <= 0:
            raise InvalidTransition("Refund ini sudah dieksekusi penuh")
        if not amount or amount > remaining:
            raise AppValidationError("Amount exceeds the remaining ordered refund", field="amount_idr")
        _refund_adjustment(session, claim, amount)
        amount_idr = amount
    elif done:
        raise InvalidTransition("Remedy ini sudah dieksekusi")
    event = RemedyEvent(claim_id=claim.id, actor_id=actor.id, action=action, amount_idr=amount_idr,
                        note=note)
    session.add(event)
    if claim.status == "decision_issued":
        claim.status, claim.resolved_at = "resolved", _now()
    session.flush()
    audit.record(session, actor=actor, action="claim.remedy_executed", target_type="claim",
                 target_id=claim.id, metadata={"action": action, "amount_idr": amount_idr,
                                               "simulated": True})
    return event


def _refund_adjustment(session, claim: Claim, amount_idr: int) -> None:
    """A partial refund lowers only the responsible party's settlement, never the whole order."""
    sale = session.scalar(select(SettlementEntry).where(
        SettlementEntry.order_id == claim.order_id, SettlementEntry.party_user_id == claim.target_user_id,
        SettlementEntry.kind == "sale"))
    if sale is None:
        return
    comm = commission(amount_idr, sale.commission_bps)
    session.add(SettlementEntry(
        order_id=claim.order_id, party_user_id=sale.party_user_id, party_role=sale.party_role,
        kind="adjustment", gross_idr=-amount_idr, commission_bps=sale.commission_bps,
        commission_idr=-comm, net_idr=-(amount_idr - comm), note="Remedy klaim (simulasi)",
        created_at=_now()))


# ---------- views ----------

def _evidence_out(session, claim: Claim, with_urls: bool) -> list[dict]:
    rows = session.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)
                           .order_by(ClaimEvidence.created_at))
    return [{"id": r.id, "uploaded_by": r.uploaded_by, "note": r.note, "file_id": r.file_id,
             "url": f"/api/v1/files/{r.file_id}?token={make_token(r.file_id)}" if with_urls else None}
            for r in rows]


def claim_out(session, claim: Claim, roles: set[str]) -> dict:
    responses = session.scalars(select(ClaimResponse).where(ClaimResponse.claim_id == claim.id)
                                .order_by(ClaimResponse.created_at, ClaimResponse.id))
    appeal_row = session.scalar(select(Appeal).where(Appeal.claim_id == claim.id))
    decision = session.scalar(select(ClaimDecision).where(ClaimDecision.claim_id == claim.id))
    remedies = session.scalars(select(RemedyEvent).where(RemedyEvent.claim_id == claim.id)
                               .order_by(RemedyEvent.created_at))
    return {
        "id": claim.id, "order_id": claim.order_id, "status": claim.status,
        "target_role": claim.target_role, "component": claim.component,
        "description": claim.description, "conversation_id": claim.conversation_id,
        "evidence": _evidence_out(session, claim, with_urls=True),
        "responses": [{"id": r.id, "kind": r.kind, "reason": r.reason, "proposal": r.proposal,
                       "buyer_decision": r.buyer_decision, "created_at": r.created_at}
                      for r in responses],
        "appeal": ({"id": appeal_row.id, "status": appeal_row.status, "reason": appeal_row.reason}
                   if appeal_row else None),
        "decision": ({"outcome": decision.outcome, "remedy_type": decision.remedy_type,
                      "amount_idr": decision.amount_idr, "reasoning": decision.reasoning,
                      "requires_execution": decision.requires_execution} if decision else None),
        "remedy_events": [{"action": e.action, "amount_idr": e.amount_idr, "note": e.note,
                           "simulated": e.simulated, "created_at": e.created_at} for e in remedies],
        "policy": {"claim_window_ends_at": claim_window_ends(session, claim.order_id),
                   "partner_response_due_at": partner_due_at(session, claim),
                   "partner_overdue": partner_overdue(session, claim),
                   "note": "Kebijakan demo yang dapat dikonfigurasi; bukan kebijakan operasional final."},
        "roles": sorted(roles), "created_at": claim.created_at, "resolved_at": claim.resolved_at,
        "simulation_notice": commerce_svc.SIMULATION_NOTICE,
    }


def appeal_summary(session, row: Appeal) -> dict:
    claim = session.get(Claim, row.claim_id)
    return {"id": row.id, "status": row.status, "basis": row.basis, "claim_id": claim.id, "order_id": claim.order_id,
            "component": claim.component, "target_role": claim.target_role, "reason": row.reason,
            "reviewer_id": row.reviewer_id, "created_at": row.created_at}


def review_bundle(session, admin: User, row: Appeal) -> dict:
    """Only what a reviewer needs; body measurements and addresses are left out."""
    if row.reviewer_id != admin.id:
        raise Forbidden("Start the review first")
    claim = session.get(Claim, row.claim_id)
    order = session.get(Order, claim.order_id)
    snap = {k: v for k, v in order.snapshot.items() if k not in ("measurements_cm", "address")}
    if isinstance(snap.get("specification"), dict):
        snap["specification"] = {k: v for k, v in snap["specification"].items()
                                 if k != "measurements_cm"}
    events = session.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id)
                             .order_by(OrderEvent.created_at, OrderEvent.id))
    shipments = session.scalars(select(Shipment).where(Shipment.order_id == order.id))
    inspections = session.scalars(select(FabricInspection).where(FabricInspection.order_id == order.id))
    amendments = session.scalars(select(OrderAmendment).where(OrderAmendment.order_id == order.id))
    messages = session.scalars(select(Message).where(Message.conversation_id == claim.conversation_id)
                               .order_by(Message.created_at, Message.id))
    audit.record(session, actor=admin, action="claim.evidence_viewed", target_type="claim",
                 target_id=claim.id)
    return {
        "appeal": appeal_summary(session, row), "claim": claim_out(session, claim, {"reviewer"}),
        "order": {"id": order.id, "kind": order.kind, "status": order.status,
                  "total_idr": order.total_idr, "approved_snapshot": snap},
        "order_events": [{"type": e.event_type, "from": e.from_status, "to": e.to_status,
                          "simulated": e.simulated, "note": e.note, "at": e.created_at} for e in events],
        "shipments": [{"leg": s.leg, "status": s.status, "tracking_no": s.tracking_no} for s in shipments],
        "inspections": [{"passed": i.passed, "condition": i.condition, "notes": i.notes,
                         "measured_width_cm": i.measured_width_cm,
                         "measured_length_m": i.measured_length_m} for i in inspections],
        "amendments": [{"reason": a.reason, "status": a.status, "price_delta_idr": a.price_delta_idr}
                       for a in amendments],
        "claim_messages": [chat_svc.message_out(m) for m in messages],
    }
