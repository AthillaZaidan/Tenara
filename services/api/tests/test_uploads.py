import io

from PIL import Image

from app.main import app
from app.services.storage import get_storage

API = "/api/v1"


def _png(size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    buf = io.BytesIO()
    Image.new("RGB", (80, 80), (10, 20, 30)).save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def _up(client, headers, kind, data, ctype, name="f"):
    return client.post(f"{API}/files", headers=headers, data={"kind": kind},
                       files={"file": (name, data, ctype)})


def test_cors_allows_the_web_app_origin_only(client):
    ok = client.options(f"{API}/auth/login", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,idempotency-key,content-type"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "idempotency-key" in ok.headers["access-control-allow-headers"].lower()
    evil = client.options(f"{API}/auth/login", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers


def test_evidence_uploads_are_private_and_signed(client, storage, make_user, auth_header):
    app.dependency_overrides[get_storage] = lambda: storage
    h = auth_header(make_user())
    r = _up(client, h, "verification_doc", _png(), "image/png")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["visibility"] == "private" and "token=" in data["url"]
    assert client.get(data["url"]).status_code == 200
    assert client.get(data["url"].split("?")[0]).status_code == 403


def test_pdf_evidence_is_accepted_only_when_it_is_really_a_pdf(client, storage, make_user, auth_header):
    app.dependency_overrides[get_storage] = lambda: storage
    h = auth_header(make_user())
    assert _up(client, h, "claim_evidence", b"%PDF-1.4 minimal", "application/pdf").status_code == 201
    assert _up(client, h, "claim_evidence", b"not a pdf", "application/pdf").status_code == 422
    assert _up(client, h, "listing_photo", b"%PDF-1.4", "application/pdf").status_code in (403, 422)


def test_images_are_cleaned_of_exif(client, storage, make_user, auth_header):
    app.dependency_overrides[get_storage] = lambda: storage
    h = auth_header(make_user())
    r = _up(client, h, "claim_evidence", _jpeg_with_exif(), "image/jpeg")
    url = r.json()["data"]["url"]
    assert not Image.open(io.BytesIO(client.get(url).content)).getexif()


def test_invalid_kinds_types_and_sizes_are_rejected(client, storage, make_user, auth_header, monkeypatch):
    app.dependency_overrides[get_storage] = lambda: storage
    h = auth_header(make_user())
    assert _up(client, h, "mystery", _png(), "image/png").status_code == 422
    assert _up(client, h, "claim_evidence", b"MZ\x90", "application/x-msdownload").status_code == 422
    assert _up(client, h, "claim_evidence", b"garbage", "image/png").status_code == 422
    monkeypatch.setattr("app.routers.files.settings.upload_max_bytes", 100)
    assert _up(client, h, "claim_evidence", _png((200, 200)), "image/png").status_code == 422
    assert client.post(f"{API}/files", data={"kind": "claim_evidence"},
                       files={"file": ("f", _png(), "image/png")}).status_code == 401


def test_listing_photos_are_public_and_merchant_only(client, storage, make_user, make_partner, auth_header):
    app.dependency_overrides[get_storage] = lambda: storage
    buyer = auth_header(make_user("buyer@example.com"))
    assert _up(client, buyer, "listing_photo", _png(), "image/png").status_code == 403
    merchant, _ = make_partner("merchant", shop="Toko Foto")
    r = _up(client, auth_header(merchant), "listing_photo", _png(), "image/png")
    data = r.json()["data"]
    assert data["visibility"] == "public" and "token" not in data["url"]
    assert client.get(data["url"]).status_code == 200  # anyone may view a public fabric photo


def test_reference_images_are_admin_only(client, storage, make_user, auth_header):
    app.dependency_overrides[get_storage] = lambda: storage
    assert _up(client, auth_header(make_user("b@example.com")), "reference_image", _png(), "image/png").status_code == 403
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    assert _up(client, auth_header(admin), "reference_image", _png(), "image/png").status_code == 201


def test_uploads_unlock_the_partner_and_listing_flows(client, session, storage, make_user, auth_header, published_entry):
    """The flows that were impossible without an upload endpoint."""
    app.dependency_overrides[get_storage] = lambda: storage
    user = make_user("ana@example.com")
    h = auth_header(user)
    doc = _up(client, h, "verification_doc", _png(), "image/png").json()["data"]
    app_body = {"type": "merchant", "data": {"shop_name": "Toko Ana", "city": "Bandung", "province": "Jawa Barat",
                                             "evidence_file_ids": [doc["id"]]}}
    created = client.post(f"{API}/partner-applications", headers=h, json=app_body).json()["data"]
    assert client.post(f"{API}/partner-applications/{created['id']}/submit", headers=h).status_code == 200
    admin = auth_header(make_user("admin@example.com", roles=(("admin", "active"),)))
    client.post(f"{API}/admin/partner-applications/{created['id']}/decision", headers=admin,
                json={"action": "approve"})
    entry = published_entry()
    listing = client.post(f"{API}/listings", headers=h, json={
        "entry_id": str(entry.id), "title": "Kain Ana", "selling_unit": "meter", "price_idr": 100000}).json()["data"]
    photo = _up(client, h, "listing_photo", _png(), "image/png").json()["data"]
    assert client.post(f"{API}/listings/{listing['id']}/images", headers=h, json={"file_id": photo["id"]}).status_code == 201
    assert client.post(f"{API}/listings/{listing['id']}/publish", headers=h).status_code == 200
