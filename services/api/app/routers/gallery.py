from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.ml.text.embedding import Embedder, get_embedder
from app.models import GalleryEntry
from app.schemas.gallery import SearchIn
from app.services import gallery as svc

router = APIRouter(tags=["gallery"])


@router.get("/gallery")
def list_gallery(
    region: str | None = Query(default=None),
    technique: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    stmt = select(GalleryEntry).where(GalleryEntry.status == "published")
    if region:
        stmt = stmt.where(func.lower(GalleryEntry.region) == region.lower())
    if technique:
        stmt = stmt.where(func.lower(GalleryEntry.technique) == technique.lower())
    if kind:
        stmt = stmt.where(GalleryEntry.kind == kind)
    page = paginate(session, GalleryEntry, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.brief(e) for e in page["items"]], "next_cursor": page["next_cursor"]})


@router.get("/gallery/{ref}")
def gallery_detail(ref: str, session: Session = Depends(get_session)):
    return ok(svc.detail(session, svc.get_published_by_ref(session, ref)))


@router.get("/gallery/{ref}/passport")
def gallery_passport(ref: str, session: Session = Depends(get_session)):
    return ok(svc.passport(session, svc.get_published_by_ref(session, ref)))


@router.get("/gallery/{ref}/variants")
def gallery_variants(ref: str, session: Session = Depends(get_session)):
    entry = svc.get_published_by_ref(session, ref)
    return ok(svc.variants(session, entry.id))


@router.post("/search/semantic")
def semantic_search(
    body: SearchIn,
    session: Session = Depends(get_session),
    embedder: Embedder | None = Depends(get_embedder),
):
    return ok(svc.search(session, embedder, body.query, region=body.region,
                         technique=body.technique, kind=body.kind, limit=body.limit))
