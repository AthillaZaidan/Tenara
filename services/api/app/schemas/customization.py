import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class CustomizationCreate(BaseModel):
    listing_id: uuid.UUID
    template_code: Literal["T01", "T02", "T03", "T04", "T05"]


class PromptChangeIn(BaseModel):
    expected_design_revision: int
    prompt: str = Field(min_length=1, max_length=1000)


class RevisionIn(BaseModel):
    expected_design_revision: int
    proposal_id: uuid.UUID | None = None
    resolutions: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None
    revert_to_revision: int | None = Field(default=None, ge=1)


class AttachMeasurements(BaseModel):
    measurement_set_id: uuid.UUID


class MeasurementCreate(BaseModel):
    height_cm: float | None = None
    values: dict[str, float | None] = {}


class MeasurementPatch(BaseModel):
    expected_revision: int
    height_cm: float | None = None
    values: dict[str, float | None] = {}


class ConfirmMeasurements(BaseModel):
    customization_id: uuid.UUID
