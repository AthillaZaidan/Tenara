import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    order_id: uuid.UUID | None = None
    request_id: uuid.UUID | None = None
    with_: Literal["merchant", "tailor"] = Field(alias="with")

    model_config = {"populate_by_name": True}


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ClaimCreate(BaseModel):
    target: Literal["merchant", "tailor"]
    component: Literal["fabric", "garment", "shipping", "service"]
    description: str = Field(min_length=5)
    evidence_file_ids: list[uuid.UUID] = []


class EvidenceIn(BaseModel):
    file_id: uuid.UUID
    note: str | None = None


class ProposalIn(BaseModel):
    remedy_type: Literal["none", "explanation", "rework", "replacement", "refund_partial",
                         "refund_full"]
    amount_idr: int | None = Field(default=None, gt=0)
    description: str | None = None


class ResponseIn(BaseModel):
    kind: Literal["discussion", "proposal", "rejection"]
    reason: str = Field(min_length=1)
    proposal: ProposalIn | None = None


class ProposalDecision(BaseModel):
    decision: Literal["accept", "reject"]


class AppealIn(BaseModel):
    partner_rejection_id: uuid.UUID
    reason: str = Field(min_length=5)
    evidence_ids: list[uuid.UUID] = []


class EvidenceRequestIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AppealDecisionIn(BaseModel):
    outcome: Literal["upheld_rejection", "overturned", "partial"]
    remedy_type: Literal["none", "explanation", "rework", "replacement", "refund_partial",
                         "refund_full"]
    amount_idr: int | None = Field(default=None, gt=0)
    reasoning: str = Field(min_length=5)


class RemedyEventIn(BaseModel):
    action: Literal["rework", "replacement", "refund_partial", "refund_full"]
    amount_idr: int | None = Field(default=None, gt=0)
    note: str | None = None


class EscalateIn(BaseModel):
    reason: str = Field(min_length=5)
