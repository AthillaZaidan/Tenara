def test_register_creates_buyer(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "Ana@Example.com", "password": "password123", "display_name": "Ana"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["email"] == "ana@example.com"
    assert data["roles"] == [{"role": "buyer", "status": "active"}]
    assert "password" not in str(data)


def test_register_duplicate_email(client):
    body = {"email": "ana@example.com", "password": "password123", "display_name": "Ana"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    r = client.post("/api/v1/auth/register", json={**body, "email": "ANA@example.com"})
    assert r.status_code == 422
    assert r.json()["error"]["field"] == "email"


def test_register_rejects_short_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "short", "display_name": "A"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["field"] == "password"


def test_login_and_me(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "ana@example.com", "password": "password123", "display_name": "Ana"},
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": "ANA@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    assert r.json()["data"]["token_type"] == "bearer"
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "ana@example.com"


def test_login_wrong_password(client, make_user):
    make_user("ana@example.com")
    r = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "nope-nope-1"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_login_unknown_email(client):
    r = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "password123"}
    )
    assert r.status_code == 401


def test_login_disabled_user(client, make_user, session):
    user = make_user("ana@example.com")
    user.status = "disabled"
    session.flush()
    r = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "password123"}
    )
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_me_rejects_garbage_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
