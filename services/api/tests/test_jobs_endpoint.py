import uuid

from app.services import jobs


def test_owner_can_read_job(client, session, make_user, auth_header):
    u = make_user()
    job = jobs.enqueue(session, "demo", u.id, {"x": 1})
    r = client.get(f"/api/v1/jobs/{job.id}", headers=auth_header(u))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == str(job.id)
    assert data["status"] == "queued"
    assert data["kind"] == "demo"


def test_other_user_gets_404(client, session, make_user, auth_header):
    a, b = make_user("a@example.com"), make_user("b@example.com")
    job = jobs.enqueue(session, "demo", a.id)
    assert client.get(f"/api/v1/jobs/{job.id}", headers=auth_header(b)).status_code == 404


def test_unknown_job_is_404(client, make_user, auth_header):
    r = client.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=auth_header(make_user()))
    assert r.status_code == 404


def test_requires_auth(client):
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 401
