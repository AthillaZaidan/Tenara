import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CustomRequestCreate(BaseModel):
    customization_id: uuid.UUID
    tailor_id: uuid.UUID
    delivery_address_id: uuid.UUID


class CustomRequestUpdate(BaseModel):
    tailor_id: uuid.UUID | None = None
    delivery_address_id: uuid.UUID | None = None


class MerchantDecisionIn(BaseModel):
    decision: Literal["confirm", "reject"]
    reason: str | None = None


class TailorDecisionIn(BaseModel):
    action: Literal["return_for_revision", "reject"]
    reason: str = Field(min_length=1)


class ExtraMaterial(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: Literal["merchant", "tailor"]
    price_idr: int = Field(ge=0)


class Surcharge(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount_idr: int = Field(ge=0)


class SpecIn(BaseModel):
    fabric_purchase_quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    finished_dimensions: dict[str, float]
    extra_materials: list[ExtraMaterial] = []
    surcharges: list[Surcharge] = []
    lead_time_days: int = Field(ge=1, le=365)
    motif_notes: str | None = None
    surplus_handling: Literal["returned_with_garment", "agreed_otherwise"] = "returned_with_garment"


class QuoteIssueIn(BaseModel):
    spec_id: uuid.UUID
    expires_in_hours: int = Field(default=48, ge=1, le=336)


class QuoteAcceptIn(BaseModel):
    expected_quote_revision: int
    acknowledged_visual_reference: bool
    delivery_address_id: uuid.UUID


class InspectionIn(BaseModel):
    passed: bool
    measured_width_cm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=1)
    measured_length_m: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    condition: str = Field(min_length=1, max_length=60)
    notes: str | None = None


class AmendmentIn(BaseModel):
    reason: str = Field(min_length=1)
    changes: dict
    price_delta_idr: int = 0


class AmendmentDecision(BaseModel):
    decision: Literal["approve", "reject"]
