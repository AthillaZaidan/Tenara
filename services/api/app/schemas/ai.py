import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ConsentIn(BaseModel):
    retention_minutes: int | None = Field(default=None, ge=1)
    share_original_with_tailor: bool = False
    allow_training_use: bool = False


class EstimateIn(BaseModel):
    body_photo_id: uuid.UUID  # front photo
    height_cm: float = Field(ge=100, le=230)
    customization_id: uuid.UUID | None = None
    # with a side photo the server fits a 3D body (SMPL-X) and estimates all seven dimensions
    side_photo_id: uuid.UUID | None = None
    gender: Literal["male", "female"] | None = None


class TryOnIn(BaseModel):
    body_photo_id: uuid.UUID


class AnalyzeIn(BaseModel):
    listing_id: uuid.UUID
    file_id: uuid.UUID | None = None


class VerifyOriginIn(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    # the curator also confirms the listing's Gallery entry is right: its photos become modern
    # reference photos for that tradition (used for matching only, never shown to other users)
    add_as_reference: bool = False
