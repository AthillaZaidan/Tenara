import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.errors import AppValidationError, InvalidTransition, NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.ml.text import story_gen
from app.ml.text.embedding import Embedder, get_embedder
from app.ml.text.story_gen import TextLLM, get_story_llm
from app.ml.vision import photo_match
from app.models import (
    CulturalSource,
    FabricListing,
    File,
    GalleryEntry,
    GalleryReferenceImage,
    GalleryVariant,
    GalleryVariantImage,
    ReferencePhoto,
    Story,
    StoryCitation,
    User,
)
from app.schemas.gallery import (
    ChunkCreate,
    Decision,
    EntryCreate,
    EntryUpdate,
    ImageAttach,
    ReferenceDecision,
    SourceCreate,
    StoryCreate,
)
from app.services import audit
from app.services import gallery as svc
from app.services.files import signed_url

router = APIRouter(prefix="/admin", tags=["admin-gallery"])
Admin = Depends(require_role("admin"))


class VariantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class VariantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


@router.get("/gallery/{entry_id}/variants")
def list_variants(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    svc.get_entry(session, entry_id)
    return ok(svc.variants(session, entry_id))


@router.post("/gallery/{entry_id}/variants", status_code=201)
def create_variant(entry_id: uuid.UUID, body: VariantCreate, user: User = Admin,
                   session: Session = Depends(get_session)):
    svc.get_entry(session, entry_id)
    name = body.name.strip()
    if not name:
        raise AppValidationError("Nama varian wajib diisi", field="name")
    existing = session.scalar(select(GalleryVariant).where(
        GalleryVariant.entry_id == entry_id, func.lower(GalleryVariant.name) == name.lower()))
    if existing:
        raise AppValidationError("Varian sudah ada", field="name")
    variant = GalleryVariant(entry_id=entry_id, name=name, description=body.description)
    session.add(variant)
    session.flush()
    audit.record(session, actor=user, action="gallery.variant_created", target_type="gallery_variant",
                 target_id=variant.id)
    session.commit()
    return ok({"id": variant.id, "entry_id": variant.entry_id, "name": variant.name,
               "description": variant.description, "images": []})


@router.patch("/gallery/variants/{variant_id}")
def update_variant(variant_id: uuid.UUID, body: VariantUpdate, user: User = Admin,
                   session: Session = Depends(get_session)):
    variant = session.get(GalleryVariant, variant_id)
    if variant is None:
        raise NotFound("Variant not found")
    name = body.name.strip()
    if not name:
        raise AppValidationError("Nama varian wajib diisi", field="name")
    existing = session.scalar(select(GalleryVariant).where(
        GalleryVariant.entry_id == variant.entry_id, GalleryVariant.id != variant.id,
        func.lower(GalleryVariant.name) == name.lower()))
    if existing:
        raise AppValidationError("Varian sudah ada", field="name")
    variant.name, variant.description = name, body.description
    session.flush()
    audit.record(session, actor=user, action="gallery.variant_updated", target_type="gallery_variant",
                 target_id=variant.id)
    session.commit()
    return ok({"id": variant.id, "entry_id": variant.entry_id, "name": variant.name,
               "description": variant.description})


@router.delete("/gallery/variants/{variant_id}")
def delete_variant(variant_id: uuid.UUID, user: User = Admin,
                   session: Session = Depends(get_session)):
    variant = session.get(GalleryVariant, variant_id)
    if variant is None:
        raise NotFound("Variant not found")
    if session.scalar(select(FabricListing.id).where(FabricListing.variant_id == variant.id).limit(1)):
        raise InvalidTransition("Pindahkan listing ke varian lain sebelum menghapus varian ini")
    session.delete(variant)
    session.flush()
    audit.record(session, actor=user, action="gallery.variant_deleted", target_type="gallery_variant",
                 target_id=variant.id)
    session.commit()
    return ok({"deleted": str(variant_id)})


@router.post("/gallery/variants/{variant_id}/images", status_code=201)
def attach_variant_image(variant_id: uuid.UUID, body: ImageAttach, user: User = Admin,
                         session: Session = Depends(get_session)):
    variant = session.get(GalleryVariant, variant_id)
    if variant is None:
        raise NotFound("Variant not found")
    file = session.get(File, body.file_id)
    if file is None or file.deleted_at is not None or file.owner_id != user.id:
        raise NotFound("File not found")
    if file.visibility != "public" or file.kind != "reference_image":
        raise AppValidationError("Gunakan gambar referensi publik", field="file_id")
    image = GalleryVariantImage(variant_id=variant.id, **body.model_dump())
    session.add(image)
    session.flush()
    audit.record(session, actor=user, action="gallery.variant_image_added", target_type="gallery_variant",
                 target_id=variant.id)
    session.commit()
    return ok({"id": image.id, "url": f"/api/v1/files/{image.file_id}"})


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


@router.delete("/gallery/{entry_id}/images/{image_id}")
def remove_entry_image(entry_id: uuid.UUID, image_id: uuid.UUID, user: User = Admin,
                       session: Session = Depends(get_session)):
    image = session.get(GalleryReferenceImage, image_id)
    if image is None or image.entry_id != entry_id:
        raise NotFound("Gallery image not found")
    session.delete(image)
    audit.record(session, actor=user, action="gallery.image_removed", target_type="gallery_entry",
                 target_id=entry_id, metadata={"image_id": str(image_id)})
    session.commit()
    return ok({"removed": str(image_id), "file_kept": True})


@router.get("/gallery/{entry_id}/images")
def list_entry_images(entry_id: uuid.UUID, user: User = Admin,
                      session: Session = Depends(get_session)):
    svc.get_entry(session, entry_id)
    return ok(svc.reference_images(session, entry_id))


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


@router.post("/gallery/{entry_id}/story/generate", status_code=201)
def generate_story(entry_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session),
                   embedder: Embedder | None = Depends(get_embedder),
                   llm: TextLLM | None = Depends(get_story_llm)):
    """Writer/critic draft from approved source chunks. Always a draft: a curator still reviews it."""
    entry = svc.get_entry(session, entry_id)
    story = story_gen.generate_story(session, user, entry, llm, embedder)
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


# ----- reference photos (photo check of a seller's tradition claim) -----

def _reference(session: Session, ref: ReferencePhoto, names: dict) -> dict:
    file = session.get(File, ref.file_id) if ref.file_id else None
    return {"id": ref.id, "entry_id": ref.entry_id, "tradition": names.get(ref.entry_id),
            "style": ref.style, "source_label": ref.source_label, "source_url": ref.source_url,
            "credit": ref.credit, "license": ref.license, "display_allowed": ref.display_allowed,
            "approval_status": ref.approval_status, "listing_id": ref.listing_id,
            "url": signed_url(file) if file and file.deleted_at is None else None,
            "created_at": ref.created_at}


def _entry_names(session: Session, ids) -> dict:
    ids = set(ids)
    if not ids:
        return {}
    return dict(session.execute(select(GalleryEntry.id, GalleryEntry.name).where(GalleryEntry.id.in_(ids))).all())


@router.get("/reference-photos")
def list_reference_photos(
    approval_status: str | None = Query(default=None),
    style: str | None = Query(default=None),
    entry_id: uuid.UUID | None = Query(default=None),
    source_label: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Admin,
    session: Session = Depends(get_session),
):
    stmt = select(ReferencePhoto)
    for column, value in ((ReferencePhoto.approval_status, approval_status), (ReferencePhoto.style, style),
                          (ReferencePhoto.entry_id, entry_id), (ReferencePhoto.source_label, source_label)):
        if value is not None:
            stmt = stmt.where(column == value)
    page = paginate(session, ReferencePhoto, stmt, limit=limit, cursor=cursor)
    names = _entry_names(session, [r.entry_id for r in page["items"]])
    return ok({"items": [_reference(session, r, names) for r in page["items"]],
               "next_cursor": page["next_cursor"]})


@router.get("/reference-photos/coverage")
def reference_coverage(user: User = Admin, session: Session = Depends(get_session)):
    """Per tradition: approved/pending counts by style, modern sources, and whether it gives a verdict."""
    rows = session.execute(
        select(ReferencePhoto.entry_id, ReferencePhoto.style, ReferencePhoto.approval_status,
               func.count(), func.count(func.distinct(ReferencePhoto.source_label)))
        .group_by(ReferencePhoto.entry_id, ReferencePhoto.style, ReferencePhoto.approval_status)).all()
    out: dict = {}
    for entry_id, style, status, count, sources in rows:
        item = out.setdefault(entry_id, {"entry_id": entry_id, "modern_approved": 0, "modern_sources": 0,
                                         "archival_approved": 0, "pending": 0, "rejected": 0})
        if status == "approved":
            item[f"{style}_approved"] += count
            if style == "modern":
                item["modern_sources"] = sources
        elif status == "pending":
            item["pending"] += count
        else:
            item["rejected"] += count
    names = _entry_names(session, out)
    items = []
    for item in out.values():
        item["tradition"] = names.get(item["entry_id"])
        item["gives_verdict"] = (item["modern_approved"] >= photo_match.MIN_REFS
                                 and item["modern_sources"] >= photo_match.MIN_SOURCES)
        items.append(item)
    items.sort(key=lambda i: (not i["gives_verdict"], -(i["modern_approved"] + i["archival_approved"])))
    return ok({"min_refs": photo_match.MIN_REFS, "min_sources": photo_match.MIN_SOURCES, "items": items})


@router.post("/reference-photos/decision")
def decide_reference_photos(body: ReferenceDecision, user: User = Admin,
                            session: Session = Depends(get_session)):
    if not body.ids and not body.source_label:
        raise AppValidationError("Pilih foto (ids) atau sumber (source_label)", field="ids")
    stmt = select(ReferencePhoto)
    if body.ids:
        stmt = stmt.where(ReferencePhoto.id.in_(body.ids))
    else:  # a whole source at once: only what is still pending
        stmt = stmt.where(ReferencePhoto.source_label == body.source_label,
                          ReferencePhoto.approval_status == "pending")
    if body.entry_id:
        stmt = stmt.where(ReferencePhoto.entry_id == body.entry_id)
    refs = list(session.scalars(stmt))
    status, now = ("approved" if body.decision == "approve" else "rejected"), datetime.now(UTC)
    for ref in refs:
        ref.approval_status, ref.decided_by, ref.decided_at = status, user.id, now
    session.flush()
    if refs:
        audit.record(session, actor=user, action=f"reference_photos.{status}",
                     target_type="reference_photo", target_id=refs[0].id,
                     metadata={"count": len(refs), "source_label": body.source_label,
                               "ids": [str(r.id) for r in refs[:50]]})
    session.commit()
    return ok({"updated": len(refs), "approval_status": status})
