import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    status: str
    output: dict | None
    error: str | None
    model_version: str | None
    attempts: int
    created_at: datetime
    finished_at: datetime | None
