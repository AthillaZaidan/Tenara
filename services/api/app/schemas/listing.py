import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ListingCreate(BaseModel):
    entry_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    selling_unit: Literal["meter", "piece"]
    price_idr: int = Field(gt=0)
    min_quantity: Decimal = Field(default=Decimal(1), gt=0, max_digits=10, decimal_places=2)
    quantity_increment: Decimal = Field(default=Decimal(1), gt=0, max_digits=10, decimal_places=2)
    material: str | None = Field(default=None, max_length=100)
    weight_gsm: int | None = Field(default=None, gt=0)
    thickness_note: str | None = Field(default=None, max_length=100)
    usable_width_cm: int | None = Field(default=None, gt=0)
    piece_length_cm: int | None = Field(default=None, gt=0)
    piece_width_cm: int | None = Field(default=None, gt=0)
    motif_orientation: str | None = Field(default=None, max_length=50)
    pattern_repeat_cm: int | None = Field(default=None, gt=0)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    dispatch_days: int = Field(default=3, ge=0, le=60)
    merchant_claimed_origin: str | None = None


class ListingUpdate(BaseModel):
    expected_revision: int
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price_idr: int | None = Field(default=None, gt=0)
    min_quantity: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    quantity_increment: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    material: str | None = Field(default=None, max_length=100)
    weight_gsm: int | None = Field(default=None, gt=0)
    thickness_note: str | None = Field(default=None, max_length=100)
    usable_width_cm: int | None = Field(default=None, gt=0)
    piece_length_cm: int | None = Field(default=None, gt=0)
    piece_width_cm: int | None = Field(default=None, gt=0)
    motif_orientation: str | None = Field(default=None, max_length=50)
    pattern_repeat_cm: int | None = Field(default=None, gt=0)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    dispatch_days: int | None = Field(default=None, ge=0, le=60)
    merchant_claimed_origin: str | None = None


class ListingImageIn(BaseModel):
    file_id: uuid.UUID
    caption: str | None = Field(default=None, max_length=300)
    sort_order: int = 0


class StockUnitIn(BaseModel):
    length_m: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    quantity: int = Field(default=1, ge=0, le=100000)


class StockUnitUpdate(BaseModel):
    quantity: int = Field(ge=0, le=100000)
