import uuid
from typing import Literal

from pydantic import BaseModel, Field


class MerchantData(BaseModel):
    shop_name: str = Field(min_length=1, max_length=200)
    description: str = ""
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=40)
    evidence_file_ids: list[uuid.UUID] = []


class TailorData(MerchantData):
    service_area: list[str] = []
    experience_years: int | None = Field(default=None, ge=0, le=80)


class ApplicationCreate(BaseModel):
    type: Literal["merchant", "tailor"]
    data: dict


class ApplicationUpdate(BaseModel):
    data: dict


class ApplicationDecision(BaseModel):
    action: Literal["start_review", "approve", "reject", "request_information"]
    reason: str | None = None


class PartnerStatusChange(BaseModel):
    user_id: uuid.UUID
    role: Literal["merchant", "tailor"]
    reason: str | None = None


class CapabilityIn(BaseModel):
    base_rate_idr: int = Field(gt=0)
    lead_time_days: int = Field(ge=1, le=365)
    weekly_capacity: int = Field(default=1, ge=1, le=1000)
    materials: list[str] = []
    supported_options: dict = {}
