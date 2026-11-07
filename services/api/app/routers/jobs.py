import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.ownership import get_owned_or_404
from app.core.responses import ok
from app.db.base import get_session
from app.models import Job, User
from app.schemas.jobs import JobOut

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    job = get_owned_or_404(session, Job, job_id, user)
    return ok(JobOut.model_validate(job).model_dump(mode="json"))
