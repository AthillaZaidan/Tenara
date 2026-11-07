import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobStatus

MAX_ATTEMPTS = 3

Handler = Callable[[Session, Job], dict]
Resolver = Callable[[Session, uuid.UUID], int]

HANDLERS: dict[str, Handler] = {}
RESOLVERS: dict[str, Resolver] = {}


def register_handler(kind: str, fn: Handler) -> None:
    HANDLERS[kind] = fn


def register_revision_resolver(subject_type: str, fn: Resolver) -> None:
    RESOLVERS[subject_type] = fn


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    session: Session,
    kind: str,
    owner_id: uuid.UUID,
    input: dict | None = None,
    *,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    subject_revision: int | None = None,
) -> Job:
    job = Job(owner_id=owner_id, kind=kind, input=input or {}, subject_type=subject_type,
              subject_id=subject_id, subject_revision=subject_revision)
    session.add(job)
    session.flush()
    session.refresh(job)
    return job


def claim_next(session: Session, now: datetime | None = None) -> Job | None:
    now = now or _now()
    job = session.scalar(
        select(Job)
        .where(Job.status == JobStatus.QUEUED.value, Job.available_at <= now)
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = JobStatus.PROCESSING.value
    job.started_at = now
    job.attempts += 1
    session.flush()
    return job


def _finish(job: Job, status: JobStatus, now: datetime, *, output=None, error=None) -> Job:
    job.status = status.value
    job.finished_at = now
    job.output = output
    job.error = error
    return job


def _superseded(session: Session, job: Job) -> bool:
    resolver = RESOLVERS.get(job.subject_type or "")
    if resolver is None or job.subject_id is None:
        return False
    return resolver(session, job.subject_id) != job.subject_revision


def run_job(session: Session, job: Job, now: datetime | None = None) -> Job:
    now = now or _now()
    handler = HANDLERS.get(job.kind)
    if handler is None:
        return _finish(job, JobStatus.FAILED, now,
                       error=f"No handler registered for kind '{job.kind}'")
    try:
        with session.begin_nested():
            output = handler(session, job)
    except Exception as exc:  # noqa: BLE001 - any handler failure is recorded on the job
        message = str(exc)
        if job.attempts < MAX_ATTEMPTS:
            job.status = JobStatus.QUEUED.value
            job.error = message
            job.available_at = now + timedelta(seconds=2**job.attempts)
            return job
        return _finish(job, JobStatus.FAILED, now, error=message)
    if _superseded(session, job):
        return _finish(job, JobStatus.COMPLETED_WITH_WARNINGS, now,
                       output={"warnings": ["superseded"]})
    output = output or {}
    status = JobStatus.COMPLETED_WITH_WARNINGS if output.get("warnings") else JobStatus.COMPLETED
    return _finish(job, status, now, output=output)


def process_one(session: Session, now: datetime | None = None) -> bool:
    job = claim_next(session, now)
    if job is None:
        return False
    run_job(session, job, now)
    session.commit()
    return True
