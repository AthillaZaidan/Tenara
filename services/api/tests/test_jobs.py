import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from app.models import User
from app.services import jobs


@pytest.fixture(autouse=True)
def clean_registries():
    handlers, resolvers = dict(jobs.HANDLERS), dict(jobs.RESOLVERS)
    yield
    jobs.HANDLERS.clear()
    jobs.HANDLERS.update(handlers)
    jobs.RESOLVERS.clear()
    jobs.RESOLVERS.update(resolvers)


def test_enqueue_creates_queued_job(session, make_user):
    u = make_user()
    job = jobs.enqueue(session, "demo", u.id, {"x": 1})
    assert job.status == "queued"
    assert job.input == {"x": 1}
    assert job.attempts == 0


def test_claim_marks_processing(session, make_user):
    jobs.enqueue(session, "demo", make_user().id)
    job = jobs.claim_next(session)
    assert job.status == "processing"
    assert job.attempts == 1
    assert job.started_at is not None
    assert jobs.claim_next(session) is None


def test_successful_job_completes(session, make_user):
    jobs.register_handler("demo", lambda s, j: {"answer": 42})
    jobs.enqueue(session, "demo", make_user().id)
    assert jobs.process_one(session) is True
    job = session.query(jobs.Job).one()
    assert job.status == "completed"
    assert job.output == {"answer": 42}
    assert job.finished_at is not None


def test_process_one_returns_false_when_empty(session):
    assert jobs.process_one(session) is False


def test_handler_warnings_complete_with_warnings(session, make_user):
    jobs.register_handler("demo", lambda s, j: {"warnings": ["low_quality"]})
    jobs.enqueue(session, "demo", make_user().id)
    jobs.process_one(session)
    assert session.query(jobs.Job).one().status == "completed_with_warnings"


def test_unknown_kind_fails_immediately(session, make_user):
    jobs.enqueue(session, "ghost", make_user().id)
    jobs.process_one(session)
    job = session.query(jobs.Job).one()
    assert job.status == "failed"
    assert "ghost" in job.error


def test_failing_handler_retries_then_fails(session, make_user):
    def boom(s, j):
        raise RuntimeError("boom")

    jobs.register_handler("demo", boom)
    jobs.enqueue(session, "demo", make_user().id)
    now = datetime.now(UTC)
    for attempt in range(1, jobs.MAX_ATTEMPTS + 1):
        assert jobs.process_one(session, now=now) is True
        job = session.query(jobs.Job).one()
        if attempt < jobs.MAX_ATTEMPTS:
            assert job.status == "queued"
            assert job.available_at > now
            now = job.available_at + timedelta(seconds=1)
    assert job.status == "failed"
    assert job.error == "boom"
    assert job.attempts == jobs.MAX_ATTEMPTS


def test_superseded_result_is_flagged(session, make_user):
    subject = uuid.uuid4()
    jobs.register_handler("demo", lambda s, j: {"preview": "x"})
    jobs.register_revision_resolver("design", lambda s, sid: 2)
    jobs.enqueue(session, "demo", make_user().id, subject_type="design", subject_id=subject,
                 subject_revision=1)
    jobs.process_one(session)
    job = session.query(jobs.Job).one()
    assert job.status == "completed_with_warnings"
    assert job.output == {"warnings": ["superseded"]}


def test_current_revision_is_not_superseded(session, make_user):
    subject = uuid.uuid4()
    jobs.register_handler("demo", lambda s, j: {"preview": "x"})
    jobs.register_revision_resolver("design", lambda s, sid: 1)
    jobs.enqueue(session, "demo", make_user().id, subject_type="design", subject_id=subject,
                 subject_revision=1)
    jobs.process_one(session)
    assert session.query(jobs.Job).one().status == "completed"


def test_two_workers_never_claim_the_same_job(engine):
    Factory = sessionmaker(engine, expire_on_commit=False)
    with Factory() as setup:
        user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x", display_name="W")
        setup.add(user)
        setup.flush()
        j1, j2 = jobs.enqueue(setup, "t", user.id), jobs.enqueue(setup, "t", user.id)
        setup.commit()
        user_id, expected = user.id, {j1.id, j2.id}
    s1, s2 = Factory(), Factory()
    try:
        a, b = jobs.claim_next(s1), jobs.claim_next(s2)
        assert a is not None and b is not None
        assert {a.id, b.id} == expected
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()
        with Factory() as cleanup:
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()
