import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AddressIn(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    recipient_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=40)
    line1: str = Field(min_length=1, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)


class CheckoutCreate(BaseModel):
    listing_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    delivery_address_id: uuid.UUID


class CheckoutConfirm(BaseModel):
    expected_total_idr: int = Field(gt=0)


class PaymentComplete(BaseModel):
    outcome: Literal["succeeded", "failed"] = "succeeded"


class OrderEventIn(BaseModel):
    event: str = Field(min_length=1, max_length=40)
    note: str | None = None


class CommissionRuleIn(BaseModel):
    applies_to: Literal["merchant_fabric", "tailoring"]
    rate_bps: int = Field(ge=0, le=5000)
