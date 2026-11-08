import uuid
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["textile", "motif", "tradition"]


class EntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Kind = "tradition"
    aliases: list[str] = []
    textile_type: str | None = Field(default=None, max_length=100)
    technique: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    community: str | None = Field(default=None, max_length=100)
    summary: str = ""


class EntryUpdate(BaseModel):
    expected_revision: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None
    aliases: list[str] | None = None
    textile_type: str | None = Field(default=None, max_length=100)
    technique: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    community: str | None = Field(default=None, max_length=100)
    summary: str | None = None


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    license: str | None = Field(default=None, max_length=100)
    rights_notes: str | None = None


class ChunkCreate(BaseModel):
    text: str = Field(min_length=1)
    locator: str | None = Field(default=None, max_length=200)
    entry_id: uuid.UUID | None = None
    metadata: dict = {}


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None


class ReferenceDecision(BaseModel):
    """Approve or reject reference photos by id, or all pending ones of a source (optionally one entry)."""
    decision: Literal["approve", "reject"]
    ids: list[uuid.UUID] = Field(default=[], max_length=500)
    source_label: str | None = Field(default=None, max_length=200)
    entry_id: uuid.UUID | None = None


class CitationIn(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    locator: str | None = Field(default=None, max_length=200)


class StoryCreate(BaseModel):
    body: str = Field(min_length=1)
    citations: list[CitationIn] = []
    unresolved: list[str] = []


class ImageAttach(BaseModel):
    file_id: uuid.UUID
    caption: str | None = Field(default=None, max_length=300)
    credit: str | None = Field(default=None, max_length=200)
    license: str | None = Field(default=None, max_length=100)
    sort_order: int = 0


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    region: str | None = None
    technique: str | None = None
    kind: Kind | None = None
    limit: int = Field(default=10, ge=1, le=50)
