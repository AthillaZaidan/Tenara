import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.errors import NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import CulturalSource, GalleryEntry, Story, StoryCitation, User
from app.schemas.gallery import (
    ChunkCreate,
    Decision,
    EntryCreate,
    EntryUpdate,
    ImageAttach,
    SourceCreate,
    StoryCreate,
)
from app.services import gallery as svc
from app.services.embedding import Embedder, get_embedder

router = APIRouter(prefix="/admin", tags=["admin-gallery"])
Admin = Depends(require_role("admin"))


def _source(s: CulturalSource) -> dict:
    return {"id": s.id, "title": s.title, "publisher": s.publisher, "url": s.url,
            "license": s.license, "rights_notes": s.rights_notes,
            "approval_status": s.approval_status, "decided_at": s.decided_at,
            "decision_reason": s.decision_reason}


def _story(session: Session, s: Story) -> dict:
    cites = session.scalars(select(StoryCitation).where(StoryCitation.story_id == s.id))
    return {"id": s.id, "entry_id": s.entry_id, "revision": s.revision, "body": s.body,
            "status": s.status, "unresolved": s.unresolved, "review_note": s.review_note,
            "reviewed_at": s.reviewed_at,
            "citations": [{"source_id": c.source_id, "chunk_id": c.chunk_id, "locator": c.locator}
                          for c in cites]}


# ----- entries -----

@router.post("/gallery", status_code=201)
def create_entry(body: EntryCreate, user: User = Admin, session: Session = Depends(get_session)):
    entry = svc.create_entry(session, user, **body.model_dump())
    session.commit()
    return ok(svc.brief(entry))


@router.get("/gallery")
def list_entries(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Admin,
    session: Session = Depends(get_session),
):
    stmt = select(GalleryEntry)
    if status:
        stmt = stmt.where(GalleryEntry.status == status)
    page = paginate(session, GalleryEntry, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.brief(e) for e in page["items"]], "next_cursor": page["next_cursor"]})


@router.get("/gallery/{entry_id}")
def get_entry(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    return ok(svc.brief(svc.get_entry(session, entry_id)))


@router.patch("/gallery/{entry_id}")
def update_entry(entry_id: uuid.UUID, body: EntryUpdate, user: User = Admin,
                 session: Session = Depends(get_session),
                 embedder: Embedder | None = Depends(get_embedder)):
    entry = svc.get_entry(session, entry_id)
    changes = body.model_dump(exclude={"expected_revision"}, exclude_none=True)
    svc.update_entry(session, user, entry, body.expected_revision, changes, embedder)
    session.commit()
    return ok(svc.brief(entry))


@router.post("/gallery/{entry_id}/publish")
def publish(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session),
            embedder: Embedder | None = Depends(get_embedder)):
    entry = svc.publish_entry(session, user, svc.get_entry(session, entry_id), embedder)
    session.commit()
    return ok(svc.brief(entry))


@router.post("/gallery/{entry_id}/archive")
def archive(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    entry = svc.archive_entry(session, user, svc.get_entry(session, entry_id))
    session.commit()
    return ok(svc.brief(entry))


@router.post("/gallery/{entry_id}/images", status_code=201)
def attach_image(entry_id: uuid.UUID, body: ImageAttach, user: User = Admin,
                 session: Session = Depends(get_session)):
    entry = svc.get_entry(session, entry_id)
    image = svc.attach_image(session, user, entry, body.file_id, caption=body.caption,
                             credit=body.credit, license=body.license, sort_order=body.sort_order)
    session.commit()
    return ok({"id": image.id, "url": f"/api/v1/files/{image.file_id}"})


# ----- sources -----

@router.post("/sources", status_code=201)
def create_source(body: SourceCreate, user: User = Admin, session: Session = Depends(get_session)):
    source = svc.create_source(session, user, **body.model_dump())
    session.commit()
    return ok(_source(source))


@router.get("/sources")
def list_sources(
    approval_status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Admin,
    session: Session = Depends(get_session),
):
    stmt = select(CulturalSource)
    if approval_status:
        stmt = stmt.where(CulturalSource.approval_status == approval_status)
    page = paginate(session, CulturalSource, stmt, limit=limit, cursor=cursor)
    return ok({"items": [_source(s) for s in page["items"]], "next_cursor": page["next_cursor"]})


@router.post("/sources/{source_id}/decision")
def decide_source(source_id: uuid.UUID, body: Decision, user: User = Admin,
                  session: Session = Depends(get_session)):
    source = session.get(CulturalSource, source_id)
    if source is None:
        raise NotFound("Source not found")
    svc.decide_source(session, user, source, body.decision, body.reason)
    session.commit()
    return ok(_source(source))


@router.post("/sources/{source_id}/chunks", status_code=201)
def add_chunk(source_id: uuid.UUID, body: ChunkCreate, user: User = Admin,
              session: Session = Depends(get_session),
              embedder: Embedder | None = Depends(get_embedder)):
    source = session.get(CulturalSource, source_id)
    if source is None:
        raise NotFound("Source not found")
    chunk = svc.add_chunk(session, source, text=body.text, locator=body.locator,
                          entry_id=body.entry_id, meta=body.metadata, embedder=embedder)
    session.commit()
    return ok({"id": chunk.id, "source_id": chunk.source_id})


# ----- stories -----

@router.post("/gallery/{entry_id}/stories", status_code=201)
def create_story(entry_id: uuid.UUID, body: StoryCreate, user: User = Admin,
                 session: Session = Depends(get_session)):
    entry = svc.get_entry(session, entry_id)
    story = svc.create_story(session, user, entry, body=body.body,
                             citations=[c.model_dump() for c in body.citations],
                             unresolved=body.unresolved)
    session.commit()
    return ok(_story(session, story))


@router.get("/gallery/{entry_id}/stories")
def list_stories(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    svc.get_entry(session, entry_id)
    rows = session.scalars(select(Story).where(Story.entry_id == entry_id)
                           .order_by(Story.revision.desc()))
    return ok([_story(session, s) for s in rows])


@router.post("/stories/{story_id}/submit")
def submit_story(story_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    story = svc.submit_story(session, user, svc.get_story(session, story_id))
    session.commit()
    return ok(_story(session, story))


@router.post("/stories/{story_id}/decision")
def decide_story(story_id: uuid.UUID, body: Decision, user: User = Admin,
                 session: Session = Depends(get_session),
                 embedder: Embedder | None = Depends(get_embedder)):
    story = svc.decide_story(session, user, svc.get_story(session, story_id), body.decision,
                             body.reason, embedder)
    session.commit()
    return ok(_story(session, story))
