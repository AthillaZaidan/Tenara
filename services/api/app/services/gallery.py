import re
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppValidationError, NotFound
from app.core.revision import check_revision
from app.ml.text.embedding import Embedder
from app.models import (
    CulturalSource,
    File,
    GalleryEntry,
    GalleryReferenceImage,
    SourceChunk,
    Story,
    StoryCitation,
    User,
)
from app.services import audit

EDITABLE_FIELDS = {"name", "kind", "aliases", "textile_type", "technique", "region", "community",
                   "summary"}


# ---------- helpers ----------

def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:100]
    return slug or "entry"


def _unique_slug(session: Session, base: str) -> str:
    slug, n = base, 2
    while session.scalar(select(GalleryEntry.id).where(GalleryEntry.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def approved_story(session: Session, entry_id: uuid.UUID) -> Story | None:
    return session.scalar(
        select(Story)
        .where(Story.entry_id == entry_id, Story.status == "approved")
        .order_by(Story.revision.desc())
        .limit(1)
    )


def _search_text(entry: GalleryEntry, story: Story | None) -> str:
    parts = [entry.name, *entry.aliases, entry.textile_type, entry.technique, entry.region,
             entry.community, entry.summary, story.body if story else None]
    return "\n".join(p for p in parts if p)


def reindex(session: Session, entry: GalleryEntry, embedder: Embedder | None) -> None:
    entry.search_text = _search_text(entry, approved_story(session, entry.id))
    entry.embedding = embedder.embed([entry.search_text])[0] if embedder else None
    session.flush()


def brief(entry: GalleryEntry) -> dict:
    return {"id": entry.id, "slug": entry.slug, "name": entry.name, "kind": entry.kind,
            "aliases": list(entry.aliases), "textile_type": entry.textile_type,
            "technique": entry.technique, "region": entry.region, "community": entry.community,
            "summary": entry.summary, "status": entry.status, "revision": entry.revision,
            "published_at": entry.published_at}


def validate_citations(session: Session, story: Story) -> list[StoryCitation]:
    cites = list(session.scalars(select(StoryCitation).where(StoryCitation.story_id == story.id)))
    if not cites:
        raise AppValidationError("A story needs at least one citation", field="citations")
    for cite in cites:
        source = session.get(CulturalSource, cite.source_id)
        if source is None or source.approval_status != "approved":
            raise AppValidationError("Every cited source must be approved", field="citations")
    return cites


# ---------- entries ----------

def create_entry(
    session: Session, actor: User | None, *, name: str, kind: str = "tradition",
    aliases: list[str] | None = None, textile_type: str | None = None,
    technique: str | None = None, region: str | None = None, community: str | None = None,
    summary: str = "", is_demo_seed: bool = False,
) -> GalleryEntry:
    entry = GalleryEntry(
        slug=_unique_slug(session, slugify(name)), name=name.strip(), kind=kind,
        aliases=aliases or [], textile_type=textile_type, technique=technique, region=region,
        community=community, summary=summary, is_demo_seed=is_demo_seed,
        created_by=actor.id if actor else None,
    )
    entry.search_text = _search_text(entry, None)
    session.add(entry)
    session.flush()
    audit.record(session, actor=actor, action="gallery.entry_created", target_type="gallery_entry",
                 target_id=entry.id, metadata={"slug": entry.slug})
    return entry


def update_entry(
    session: Session, actor: User, entry: GalleryEntry, expected_revision: int, changes: dict,
    embedder: Embedder | None,
) -> GalleryEntry:
    if entry.status == "archived":
        raise AppValidationError("Archived entries cannot be edited", field="status")
    check_revision(expected_revision, entry.revision)
    for key, value in changes.items():
        if key in EDITABLE_FIELDS and value is not None:
            setattr(entry, key, value)
    entry.revision += 1
    if entry.status == "published":
        reindex(session, entry, embedder)
    else:
        entry.search_text = _search_text(entry, approved_story(session, entry.id))
    session.flush()
    audit.record(session, actor=actor, action="gallery.entry_updated", target_type="gallery_entry",
                 target_id=entry.id, metadata={"fields": sorted(changes)})
    return entry


def publish_entry(
    session: Session, actor: User | None, entry: GalleryEntry, embedder: Embedder | None,
    *, action: str = "gallery.published",
) -> GalleryEntry:
    if entry.status == "published":
        return entry
    if entry.status == "archived":
        raise AppValidationError("Archived entries cannot be published", field="status")
    story = approved_story(session, entry.id)
    if story is None:
        raise AppValidationError("Publishing needs an approved story", field="story")
    validate_citations(session, story)
    entry.status = "published"
    entry.published_at = datetime.now(UTC)
    entry.revision += 1
    reindex(session, entry, embedder)
    audit.record(session, actor=actor, action=action, target_type="gallery_entry",
                 target_id=entry.id)
    return entry


def archive_entry(session: Session, actor: User, entry: GalleryEntry) -> GalleryEntry:
    entry.status = "archived"
    entry.revision += 1
    session.flush()
    audit.record(session, actor=actor, action="gallery.archived", target_type="gallery_entry",
                 target_id=entry.id)
    return entry


def attach_image(
    session: Session, actor: User, entry: GalleryEntry, file_id: uuid.UUID, *,
    caption: str | None, credit: str | None, license: str | None, sort_order: int,
) -> GalleryReferenceImage:
    file = session.get(File, file_id)
    if file is None or file.deleted_at is not None:
        raise NotFound("File not found")
    if file.visibility != "public":
        raise AppValidationError("Gallery reference images must be public files", field="file_id")
    image = GalleryReferenceImage(entry_id=entry.id, file_id=file_id, caption=caption,
                                  credit=credit, license=license, sort_order=sort_order)
    session.add(image)
    session.flush()
    audit.record(session, actor=actor, action="gallery.image_attached",
                 target_type="gallery_entry", target_id=entry.id, metadata={"file_id": str(file_id)})
    return image


def get_entry(session: Session, entry_id: uuid.UUID) -> GalleryEntry:
    entry = session.get(GalleryEntry, entry_id)
    if entry is None:
        raise NotFound("Gallery entry not found")
    return entry


def get_published_by_ref(session: Session, ref: str) -> GalleryEntry:
    try:
        cond = GalleryEntry.id == uuid.UUID(ref)
    except ValueError:
        cond = GalleryEntry.slug == ref
    entry = session.scalar(select(GalleryEntry).where(cond, GalleryEntry.status == "published"))
    if entry is None:
        raise NotFound("Gallery entry not found")
    return entry


# ---------- sources & chunks ----------

def create_source(session: Session, actor: User | None, *, title: str, publisher: str | None = None,
                  url: str | None = None, license: str | None = None,
                  rights_notes: str | None = None) -> CulturalSource:
    source = CulturalSource(title=title, publisher=publisher, url=url, license=license,
                            rights_notes=rights_notes, created_by=actor.id if actor else None)
    session.add(source)
    session.flush()
    audit.record(session, actor=actor, action="source.created", target_type="cultural_source",
                 target_id=source.id)
    return source


def decide_source(session: Session, actor: User | None, source: CulturalSource, decision: str,
                  reason: str | None, *, action_prefix: str = "source") -> CulturalSource:
    if decision == "reject":
        if not reason:
            raise AppValidationError("A reason is required to reject a source", field="reason")
        blocking = session.scalar(
            select(func.count())
            .select_from(StoryCitation)
            .join(Story, Story.id == StoryCitation.story_id)
            .join(GalleryEntry, GalleryEntry.id == Story.entry_id)
            .where(StoryCitation.source_id == source.id, Story.status == "approved",
                   GalleryEntry.status == "published")
        )
        if blocking:
            raise AppValidationError("Source is cited by published content", field="decision")
    source.approval_status = "approved" if decision == "approve" else "rejected"
    source.decided_by = actor.id if actor else None
    source.decided_at = datetime.now(UTC)
    source.decision_reason = reason
    session.flush()
    audit.record(session, actor=actor, action=f"{action_prefix}.{source.approval_status}",
                 target_type="cultural_source", target_id=source.id, metadata={"reason": reason})
    return source


def add_chunk(session: Session, source: CulturalSource, *, text: str, locator: str | None = None,
              entry_id: uuid.UUID | None = None, meta: dict | None = None,
              embedder: Embedder | None = None) -> SourceChunk:
    chunk = SourceChunk(source_id=source.id, entry_id=entry_id, text=text, locator=locator,
                        meta=meta or {},
                        embedding=embedder.embed([text])[0] if embedder else None)
    session.add(chunk)
    session.flush()
    return chunk


# ---------- stories ----------

def create_story(session: Session, actor: User | None, entry: GalleryEntry, *, body: str,
                 citations: list[dict], unresolved: list[str] | None = None) -> Story:
    for cite in citations:
        source = session.get(CulturalSource, cite["source_id"])
        if source is None:
            raise AppValidationError("Cited source does not exist", field="citations")
        if cite.get("chunk_id"):
            chunk = session.get(SourceChunk, cite["chunk_id"])
            if chunk is None or chunk.source_id != source.id:
                raise AppValidationError("Cited chunk does not belong to the source",
                                         field="citations")
    revision = (session.scalar(select(func.max(Story.revision)).where(Story.entry_id == entry.id))
                or 0) + 1
    story = Story(entry_id=entry.id, revision=revision, body=body, unresolved=unresolved or [],
                  author_id=actor.id if actor else None)
    session.add(story)
    session.flush()
    for cite in citations:
        session.add(StoryCitation(story_id=story.id, source_id=cite["source_id"],
                                  chunk_id=cite.get("chunk_id"), locator=cite.get("locator")))
    session.flush()
    audit.record(session, actor=actor, action="story.created", target_type="story",
                 target_id=story.id, metadata={"entry_id": str(entry.id), "revision": revision})
    return story


def get_story(session: Session, story_id: uuid.UUID) -> Story:
    story = session.get(Story, story_id)
    if story is None:
        raise NotFound("Story not found")
    return story


def submit_story(session: Session, actor: User, story: Story) -> Story:
    if story.status != "draft":
        raise AppValidationError("Only draft stories can be submitted", field="status")
    story.status = "in_review"
    session.flush()
    audit.record(session, actor=actor, action="story.submitted", target_type="story",
                 target_id=story.id)
    return story


def decide_story(session: Session, actor: User | None, story: Story, decision: str,
                 note: str | None, embedder: Embedder | None) -> Story:
    if story.status != "in_review":
        raise AppValidationError("Only stories in review can be decided", field="status")
    if decision == "reject":
        if not note:
            raise AppValidationError("A reason is required to reject a story", field="reason")
        story.status = "rejected"
    else:
        validate_citations(session, story)
        for older in session.scalars(select(Story).where(
                Story.entry_id == story.entry_id, Story.status == "approved")):
            older.status = "superseded"
        story.status = "approved"
    story.reviewed_by = actor.id if actor else None
    story.reviewed_at = datetime.now(UTC)
    story.review_note = note
    session.flush()
    entry = session.get(GalleryEntry, story.entry_id)
    if story.status == "approved" and entry.status == "published":
        reindex(session, entry, embedder)
    audit.record(session, actor=actor, action=f"story.{story.status}", target_type="story",
                 target_id=story.id, metadata={"note": note})
    return story


# ---------- public views ----------

def reference_images(session: Session, entry_id: uuid.UUID) -> list[dict]:
    rows = session.scalars(select(GalleryReferenceImage)
                           .where(GalleryReferenceImage.entry_id == entry_id)
                           .order_by(GalleryReferenceImage.sort_order, GalleryReferenceImage.id))
    return [{"id": r.id, "url": f"/api/v1/files/{r.file_id}", "caption": r.caption, "credit": r.credit,
             "license": r.license} for r in rows]


def variants(session: Session, entry_id: uuid.UUID) -> list[dict]:
    from app.models import GalleryVariant, GalleryVariantImage

    rows = session.scalars(select(GalleryVariant).where(GalleryVariant.entry_id == entry_id)
                           .order_by(GalleryVariant.name, GalleryVariant.id))
    result = []
    for variant in rows:
        images = session.scalars(select(GalleryVariantImage)
                                 .where(GalleryVariantImage.variant_id == variant.id)
                                 .order_by(GalleryVariantImage.sort_order, GalleryVariantImage.id))
        result.append({"id": variant.id, "entry_id": variant.entry_id, "name": variant.name,
                       "description": variant.description,
                       "images": [{"url": f"/api/v1/files/{image.file_id}",
                                   "caption": image.caption, "credit": image.credit,
                                   "license": image.license} for image in images]})
    return result


def detail(session: Session, entry: GalleryEntry) -> dict:
    story = approved_story(session, entry.id)
    from app.services.listings import (
        entry_availability,  # local import: listings depends on gallery
    )

    return {**brief(entry), "has_story": story is not None,
            "reference_images": reference_images(session, entry.id),
            "availability": entry_availability(session, entry.id)}


def passport(session: Session, entry: GalleryEntry) -> dict:
    story = approved_story(session, entry.id)
    citations = []
    if story:
        for cite in session.scalars(select(StoryCitation).where(StoryCitation.story_id == story.id)):
            source = session.get(CulturalSource, cite.source_id)
            chunk = session.get(SourceChunk, cite.chunk_id) if cite.chunk_id else None
            citations.append({"source_id": source.id, "title": source.title,
                              "publisher": source.publisher, "url": source.url,
                              "license": source.license, "locator": cite.locator,
                              "excerpt": chunk.text if chunk else None})
    return {
        "entry": brief(entry),
        "story": ({"revision": story.revision, "body": story.body,
                   "unresolved": story.unresolved} if story else None),
        "citations": citations,
        "reference_images": reference_images(session, entry.id),
        "review": {"status": "reviewed" if story else "unreviewed",
                   "reviewed_at": story.reviewed_at if story else None,
                   "published_at": entry.published_at, "is_demo_seed": entry.is_demo_seed},
        "notice": ("Gallery content describes a cultural reference. It does not certify the "
                   "origin or authenticity of any specific physical item."),
    }


# ---------- search ----------

def search(session: Session, embedder: Embedder | None, query: str, *, region: str | None = None,
           technique: str | None = None, kind: str | None = None, limit: int = 10) -> dict:
    q = query.strip()
    if not q:
        raise AppValidationError("Query must not be empty", field="query")
    filters = [GalleryEntry.status == "published"]
    if region:
        filters.append(func.lower(GalleryEntry.region) == region.lower())
    if technique:
        filters.append(func.lower(GalleryEntry.technique) == technique.lower())
    if kind:
        filters.append(GalleryEntry.kind == kind)

    tsq = func.plainto_tsquery("simple", q)
    tsv = func.to_tsvector("simple", GalleryEntry.search_text)
    cols = [GalleryEntry, func.ts_rank_cd(tsv, tsq).label("rank"), tsv.op("@@")(tsq).label("kw")]
    if embedder:
        qvec = embedder.embed([q])[0]
        cols.append((1 - GalleryEntry.embedding.cosine_distance(qvec)).label("sim"))
    rows = session.execute(select(*cols).where(*filters)).all()

    # Short source chunks embed far better than a long entry text (models truncate ~128 tokens),
    # and they double as cited evidence for the match explanation.
    best_chunk: dict[uuid.UUID, tuple[float, str, str]] = {}
    if embedder:
        csim = (1 - SourceChunk.embedding.cosine_distance(qvec)).label("sim")
        chunk_rows = session.execute(
            select(SourceChunk.entry_id, SourceChunk.text, CulturalSource.title, csim)
            .join(CulturalSource, CulturalSource.id == SourceChunk.source_id)
            .join(GalleryEntry, GalleryEntry.id == SourceChunk.entry_id)
            .where(*filters, CulturalSource.approval_status == "approved",
                   SourceChunk.embedding.is_not(None))
        ).all()
        for c in chunk_rows:
            if c.entry_id not in best_chunk or float(c.sim) > best_chunk[c.entry_id][0]:
                best_chunk[c.entry_id] = (float(c.sim), c.text, c.title)

    max_rank = max((r.rank for r in rows), default=0) or 1.0
    scored = []
    for row in rows:
        sim = float(row.sim) if embedder and row.sim is not None else None
        evidence = None
        chunk = best_chunk.get(row[0].id)
        if chunk and (sim is None or chunk[0] > sim):
            sim, evidence = chunk[0], {"text": chunk[1], "source": chunk[2]}
        semantic_ok = sim is not None and sim >= settings.search_min_similarity
        if not (row.kw or semantic_ok):
            continue
        kw_part = row.rank / max_rank if row.kw else 0.0
        score = 0.6 * max(sim or 0.0, 0.0) + 0.4 * kw_part if embedder else kw_part
        kind_ = "hybrid" if (row.kw and semantic_ok) else "keyword" if row.kw else "semantic"
        scored.append((score, row[0], kind_, sim, evidence))
    scored.sort(key=lambda t: t[0], reverse=True)

    results = []
    for score, entry, kind_, sim, evidence in scored[: max(1, min(limit, 50))]:
        if kind_ == "semantic":
            snippet = evidence["text"][:240] if evidence else entry.summary[:240]
        else:
            snippet = session.scalar(select(func.ts_headline(
                "simple", entry.search_text, tsq, "MaxWords=30,MinWords=10")))
        results.append({"entry": brief(entry), "score": round(score, 4),
                        "match": {"type": kind_, "similarity": None if sim is None else round(sim, 4),
                                  "snippet": snippet, "evidence": evidence}})
    response = {"mode": "hybrid" if embedder else "keyword", "results": results}
    if not results:
        response["explanation"] = "Tidak ada entri Gallery terbit yang cocok dengan pencarian ini."
    return response
