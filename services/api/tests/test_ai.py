import io
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select
from test_customization import (  # noqa: F401  (fixtures + helpers shared with the customization tests)
    _apply,
    _create,
    buyer,
    entry,
    h,
    make_listing,
    synced,
)

from app.core.config import settings
from app.main import app
from app.ml.vision import render
from app.ml.vision.pose import Landmark, PoseResult, get_pose_detector
from app.ml.vision.vlm import get_vlm
from app.models import (
    AuditEvent,
    BodyPhoto,
    File,
    GalleryEntry,
    Job,
    ListingImage,
    MeasurementSet,
    Preview,
)
from app.services import jobs, photos, template_defs
from app.services.files import create_file
from app.services.storage import get_storage
from app.workers import handlers

API = "/api/v1"
ASSET = Path(__file__).parent / "assets" / "standing_front.jpg"
REAL_MODEL = Path(settings.pose_model_path)


# ---------- helpers ----------

def _jpeg(size=(600, 900), color=(120, 100, 90)) -> bytes:
    img = Image.new("RGB", size, color)
    ImageDraw.Draw(img).rectangle((200, 200, 400, 600), fill=(60, 60, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _pose(count=1, ankles=1.0, shoulder_vis=1.0, shoulder_x=(0.33, 0.67), hip_y=0.52) -> PoseResult:
    marks = {
        "nose": Landmark(0.5, 0.12, 1.0),
        "l_shoulder": Landmark(shoulder_x[1], 0.25, shoulder_vis),
        "r_shoulder": Landmark(shoulder_x[0], 0.25, shoulder_vis),
        "l_hip": Landmark(0.57, hip_y, 1.0), "r_hip": Landmark(0.43, hip_y, 1.0),
        "l_ankle": Landmark(0.55, 0.95, ankles), "r_ankle": Landmark(0.45, 0.95, ankles),
        "l_elbow": Landmark(0.7, 0.4, 1.0), "r_elbow": Landmark(0.3, 0.4, 1.0),
        "l_wrist": Landmark(0.72, 0.55, 1.0), "r_wrist": Landmark(0.28, 0.55, 1.0),
    }
    return PoseResult(count, marks if count else {}, "fake-pose/1")


class FakeDetector:
    model_version = "fake-pose/1"

    def __init__(self, result: PoseResult):
        self.result = result

    def detect(self, image):
        return self.result


@pytest.fixture
def ai(client, session, storage, monkeypatch):
    app.dependency_overrides[get_storage] = lambda: storage
    monkeypatch.setattr(handlers, "_storage", lambda: storage)
    return storage


def use_pose(monkeypatch, result: PoseResult | None):
    monkeypatch.setattr(handlers, "get_pose_detector", lambda: None if result is None else FakeDetector(result))


def run_jobs(session) -> int:
    n = 0
    while jobs.process_one(session):
        n += 1
    return n


def _consent(client, h, **body):
    r = client.post(f"{API}/photo-consents", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _upload(client, h, consent_id, data=None, ctype="image/jpeg"):
    return client.post(f"{API}/body-photos", headers=h, data={"consent_id": consent_id},
                       files={"file": ("photo.jpg", data or _jpeg(), ctype)})


def _photo(client, h, **consent):
    c = _consent(client, h, **consent)
    r = _upload(client, h, c["id"])
    assert r.status_code == 201, r.text
    return r.json()["data"], c


def _job_error(session, job_id):
    session.expire_all()
    return session.get(Job, job_id)


# ---------- consent + photo intake ----------

def test_consent_notice_is_public_and_explains_privacy(client):
    data = client.get(f"{API}/photo-consent-notice").json()["data"]
    assert "privat" in data["text"] and data["default_retention_minutes"] == 60
    assert any("seluruh badan" in g.lower() for g in data["guidance"])


def test_consent_retention_is_bounded(client, ai, h):
    assert client.post(f"{API}/photo-consents", headers=h, json={"retention_minutes": 0}).status_code == 422
    too_long = settings.photo_max_retention_days * 1440 + 1
    assert client.post(f"{API}/photo-consents", headers=h, json={"retention_minutes": too_long}).status_code == 422
    assert _consent(client, h)["retention_minutes"] == 60  # short default window


def test_upload_requires_valid_consent_and_a_good_photo(client, ai, h, make_user, auth_header):
    c = _consent(client, h)
    other = auth_header(make_user("other@example.com"))
    assert _upload(client, other, c["id"]).status_code == 404  # someone else's consent
    assert _upload(client, h, c["id"], ctype="application/pdf").status_code == 422
    assert _upload(client, h, c["id"], data=b"not an image").status_code == 422
    assert _upload(client, h, c["id"], data=_jpeg((200, 300))).status_code == 422  # too small
    assert _upload(client, h, c["id"], data=_jpeg((900, 500))).status_code == 422  # landscape
    assert _upload(client, h, c["id"], data=b"x" * (settings.photo_max_bytes + 5)).status_code == 422
    assert _upload(client, h, c["id"]).status_code == 201
    assert client.post(f"{API}/body-photos", headers=h, data={"consent_id": c["id"]}).status_code == 422


def test_uploaded_photo_is_private_and_stripped_of_exif(client, session, ai, h):
    img = Image.new("RGB", (600, 900), (10, 20, 30))
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    consent = _consent(client, h)
    photo = _upload(client, h, consent["id"], buf.getvalue()).json()["data"]
    row = session.get(BodyPhoto, photo["id"])
    stored = session.get(File, row.file_id)
    assert stored.visibility == "private" and stored.kind == "body_photo"
    assert client.get(f"{API}/files/{stored.id}").status_code == 403
    reopened = Image.open(io.BytesIO(ai.open(stored.storage_key)))
    assert not reopened.getexif()  # metadata (incl. GPS) was dropped on re-encode


def test_default_retention_window_is_set(client, session, ai, h):
    photo, _c = _photo(client, h)
    row = session.get(BodyPhoto, photo["id"])
    assert timedelta(minutes=58) < row.delete_after - row.created_at.replace(tzinfo=row.delete_after.tzinfo) < timedelta(minutes=61)


def test_photos_are_owner_scoped(client, ai, h, make_user, auth_header):
    photo, _ = _photo(client, h)
    other = auth_header(make_user("other@example.com"))
    assert client.delete(f"{API}/body-photos/{photo['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/body-photos", headers=other).json()["data"] == []
    assert len(client.get(f"{API}/body-photos", headers=h).json()["data"]) == 1


def test_deleting_a_photo_removes_raw_and_derived_images_but_keeps_order_history(client, session, ai, h, monkeypatch, make_listing):
    use_pose(monkeypatch, _pose())
    cust = _create(client, h, make_listing())
    photo, _ = _photo(client, h)
    _add_texture(session, make_listing, cust)
    mset = _estimate_ok(client, session, h, photo)
    client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h, json={"body_photo_id": photo["id"]})
    run_jobs(session)
    preview = session.scalar(select(Preview).where(Preview.kind == "on_body"))
    assert preview.file_id is not None
    raw = session.get(BodyPhoto, photo["id"]).file_id
    assert client.delete(f"{API}/body-photos/{photo['id']}", headers=h).status_code == 200
    session.expire_all()
    assert session.get(File, raw).deleted_at is not None
    assert session.get(Preview, preview.id).file_id is None
    assert session.get(Preview, preview.id).status == "deleted_with_photo"
    assert session.get(MeasurementSet, mset) is not None  # the written measurements survive
    assert client.delete(f"{API}/body-photos/{photo['id']}", headers=h).status_code == 404


def test_revoking_consent_deletes_its_photos(client, session, ai, h):
    photo, c = _photo(client, h)
    r = client.post(f"{API}/photo-consents/{c['id']}/revoke", headers=h)
    assert r.json()["data"] == {"revoked": True, "photos_deleted": 1}
    assert session.get(BodyPhoto, photo["id"]).status == "deleted"
    assert _upload(client, h, c["id"]).status_code == 409  # revoked consent cannot be reused


def test_expired_photos_are_purged_automatically(client, session, ai, h):
    photo, _ = _photo(client, h)
    row = session.get(BodyPhoto, photo["id"])
    assert photos.purge_expired(session, ai) == 0
    row.delete_after = row.delete_after - timedelta(hours=3)
    session.flush()
    assert photos.purge_expired(session, ai) == 1
    assert row.status == "deleted" and row.file_id is None
    event = session.scalar(select(AuditEvent).where(AuditEvent.action == "photo.deleted"))
    assert event.meta["reason"] == "retention_expired"


# ---------- automatic measurement ----------

def _estimate(client, h, photo, height=170):
    r = client.post(f"{API}/body-measurements/estimate", headers=h,
                    json={"body_photo_id": photo["id"], "height_cm": height})
    assert r.status_code == 202, r.text
    return r.json()["data"]["job_id"]


def _estimate_ok(client, session, h, photo, height=170):
    job_id = _estimate(client, h, photo, height)
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["status"] in ("completed", "completed_with_warnings"), out
    return out["measurement_set"]["id"]


def _values(out):
    return {v["key"]: v for v in out["measurement_set"]["values"]}


def test_estimate_returns_only_supported_dimensions_and_marks_the_rest_manual(client, session, ai, h, monkeypatch):
    use_pose(monkeypatch, _pose())
    photo, _ = _photo(client, h)
    job_id = _estimate(client, h, photo)
    assert client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]["status"] == "queued"
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["status"] == "completed_with_warnings" and out["model_version"] == "fake-pose/1"
    v = _values(out)
    # 600x900 image, 170 cm: height_px=(0.95-0.12)*900/0.897 -> 4.899 px/cm
    assert v["shoulder_width"]["value_cm"] == pytest.approx(41.6, abs=0.3)
    assert v["back_length"]["value_cm"] == pytest.approx(49.6, abs=0.3)
    assert v["shoulder_width"]["source"] == "estimated" and v["shoulder_width"]["quality_flag"] == "review_required"
    for key in ("chest_circumference", "waist_circumference", "hip_circumference", "sleeve_length", "neck_circumference"):
        assert v[key]["value_cm"] is None and v[key]["source"] == "manual_required"
        assert v[key]["quality_flag"] == "unsupported"  # never invented
    assert "buyer_review_required" in out["output"]["warnings"]
    assert set(out["output"]["manual_required"]) >= {"chest_circumference", "sleeve_length"}


def test_hidden_legs_lower_confidence_and_warn(client, session, ai, h, monkeypatch):
    use_pose(monkeypatch, _pose(ankles=0.2))
    photo, _ = _photo(client, h)
    job_id = _estimate(client, h, photo)
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["output"]["scale_basis"] == "torso_proportion"
    assert any("scale_from_torso_proportion" in w for w in out["output"]["warnings"])
    assert _values(out)["shoulder_width"]["quality_flag"] == "low_confidence"


def test_implausible_results_are_not_returned_as_measurements(client, session, ai, h, monkeypatch):
    use_pose(monkeypatch, _pose())
    photo, _ = _photo(client, h)
    job_id = _estimate(client, h, photo, height=100)  # height contradicts the picture
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    v = _values(out)
    assert v["shoulder_width"]["value_cm"] is None and v["shoulder_width"]["quality_flag"] == "implausible"
    assert any("shoulder_width_implausible" in w for w in out["output"]["warnings"])


@pytest.mark.parametrize("pose,message", [
    (_pose(count=0), "Tidak ada orang"),
    (_pose(count=2), "lebih dari satu orang"),
    (_pose(shoulder_vis=0.2), "Bahu dan pinggul"),
])
def test_unusable_photos_fail_honestly_without_retry_or_fake_output(client, session, ai, h, monkeypatch, pose, message):
    use_pose(monkeypatch, pose)
    photo, _ = _photo(client, h)
    job_id = _estimate(client, h, photo)
    run_jobs(session)
    job = _job_error(session, job_id)
    assert job.status == "failed" and message in job.error and job.attempts == 1
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["measurement_set"] is None
    assert session.scalar(select(MeasurementSet)) is None


def test_missing_pose_model_is_reported_not_faked(client, session, ai, h, monkeypatch):
    use_pose(monkeypatch, None)
    photo, _ = _photo(client, h)
    job_id = _estimate(client, h, photo)
    run_jobs(session)
    job = _job_error(session, job_id)
    assert job.status == "failed" and "Model pose belum terpasang" in job.error
    assert session.scalar(select(MeasurementSet)) is None


def test_estimate_validates_input_and_ownership(client, ai, h, make_user, auth_header):
    photo, _ = _photo(client, h)
    other = auth_header(make_user("other@example.com"))
    assert client.post(f"{API}/body-measurements/estimate", headers=other,
                       json={"body_photo_id": photo["id"], "height_cm": 170}).status_code == 404
    assert client.post(f"{API}/body-measurements/estimate", headers=h,
                       json={"body_photo_id": photo["id"], "height_cm": 20}).status_code == 422
    job_id = _estimate(client, h, photo)
    assert client.get(f"{API}/body-measurements/{job_id}", headers=other).status_code == 404


def test_estimated_values_flow_into_review_and_correction(client, session, ai, h, monkeypatch):
    use_pose(monkeypatch, _pose())
    photo, _ = _photo(client, h)
    mset_id = _estimate_ok(client, session, h, photo)
    r = client.patch(f"{API}/measurement-sets/{mset_id}", headers=h, json={
        "expected_revision": 1, "values": {"shoulder_width": 43.0, "chest_circumference": 96}})
    v = {x["key"]: x for x in r.json()["data"]["values"]}
    assert v["shoulder_width"]["source"] == "corrected" and v["shoulder_width"]["original_value_cm"] == pytest.approx(41.6, abs=0.3)
    assert v["chest_circumference"]["source"] == "manual"  # the buyer supplies what the model cannot


@pytest.mark.skipif(not REAL_MODEL.exists() or not ASSET.exists(), reason="pose model/test photo not installed")
def test_real_pose_model_runs_on_a_public_domain_photo(client, session, ai, h):
    get_pose_detector.cache_clear()
    consent = _consent(client, h)
    photo = _upload(client, h, consent["id"], ASSET.read_bytes()).json()["data"]
    job_id = _estimate(client, h, photo, height=165)
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["status"] == "completed_with_warnings", out
    assert out["model_version"].startswith("mediapipe-pose-landmarker-full/")
    v = _values(out)
    assert 25 <= v["shoulder_width"]["value_cm"] <= 70 and 25 <= v["back_length"]["value_cm"] <= 90
    assert v["chest_circumference"]["source"] == "manual_required"


# ---------- previews ----------

def _fabric_png() -> bytes:
    img = Image.new("RGB", (300, 300), (150, 40, 40))
    d = ImageDraw.Draw(img)
    for x in range(0, 300, 30):
        d.rectangle((x, 0, x + 12, 300), fill=(230, 190, 60))
    for y in range(0, 300, 40):
        d.line((0, y, 300, y), fill=(20, 20, 20), width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _add_texture(session, make_listing, cust):
    from app.models import Customization

    listing_id = session.get(Customization, cust["id"]).listing_id
    merchant_user_id = session.get(__import__("app.models", fromlist=["FabricListing"]).FabricListing, listing_id)
    owner = session.get(__import__("app.models", fromlist=["MerchantProfile"]).MerchantProfile, merchant_user_id.merchant_id).user_id
    stored = create_file(session, handlers._storage(), owner_id=owner, kind="listing_photo",
                         data=_fabric_png(), content_type="image/png", visibility="public")
    session.add(ListingImage(listing_id=listing_id, file_id=stored.id))
    session.flush()


def _product_preview(client, h, cust):
    r = client.post(f"{API}/customizations/{cust['id']}/product-previews", headers=h)
    assert r.status_code == 202
    return r.json()["data"]


def test_product_preview_uses_the_listings_own_fabric(client, session, ai, h, make_listing):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    preview = _product_preview(client, h, cust)
    assert preview["status"] == "queued" and preview["url"] is None
    run_jobs(session)
    done = client.get(f"{API}/previews/{preview['id']}", headers=h).json()["data"]
    assert done["status"] == "completed" and done["method"] == "pillow_flat_composite_v1"
    assert done["url"] and "konseptual" in done["warnings"][0].lower()
    png = client.get(done["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(png.content))
    assert img.size == (600, 800)
    colors = {img.getpixel((245, y))[:3] for y in range(200, 500, 7)}
    assert len(colors) > 3  # real fabric texture, not a flat fill


def test_each_revision_gets_its_own_preview_and_old_ones_go_stale(client, session, ai, h, make_listing):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    first = _product_preview(client, h, cust)
    run_jobs(session)
    _apply(client, h, cust["id"], 1, changes={"pockets": "double_chest", "hem_length_delta_cm": 5})
    assert client.get(f"{API}/previews/{first['id']}", headers=h).json()["data"]["status"] == "stale"
    second = _product_preview(client, h, cust)
    run_jobs(session)
    a = client.get(client.get(f"{API}/previews/{first['id']}", headers=h).json()["data"]["url"] or "/api/v1/health")
    assert a.status_code in (200, 403)
    new = client.get(f"{API}/previews/{second['id']}", headers=h).json()["data"]
    assert new["status"] == "completed" and new["design_revision"] == 2


def test_preview_fails_honestly_when_listing_has_no_photo(client, session, ai, h, make_listing):
    cust = _create(client, h, make_listing())
    preview = _product_preview(client, h, cust)
    run_jobs(session)
    out = client.get(f"{API}/previews/{preview['id']}", headers=h).json()["data"]
    assert out["status"] == "failed" and any("foto kain" in w for w in out["warnings"])
    assert out["url"] is None


def test_superseded_preview_job_is_flagged_when_design_changed_meanwhile(client, session, ai, h, make_listing):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    _product_preview(client, h, cust)
    _apply(client, h, cust["id"], 1, changes={"collar": "none"})
    run_jobs(session)
    job = session.scalar(select(Job).where(Job.kind == "preview.product"))
    assert job.status == "completed_with_warnings" and job.output == {"warnings": ["superseded"]}


@pytest.mark.parametrize("code", sorted(template_defs.DEFINITIONS))
def test_every_template_renders_every_option_without_errors(code):
    texture = render.load_texture(_fabric_png())
    defn = template_defs.definition(code)
    base = template_defs.defaults(defn)
    baseline = render.to_png(render.render_garment(code, base, texture).image)
    for field, spec in defn["options"].items():
        values = spec["values"] if spec["type"] == "enum" else [spec["min"], spec["max"]]
        for value in values:
            result = render.render_garment(code, {**base, field: value}, texture)
            assert result.image.size == (600, 800) and result.warnings == []
            if value != base[field] and field in ("pockets", "hem_length_delta_cm", "collar", "motif_placement"):
                assert render.to_png(result.image) != baseline, f"{code}.{field}={value} not visible"


def test_unknown_options_are_disclosed_not_silently_dropped():
    texture = render.load_texture(_fabric_png())
    result = render.render_garment("T01", {"collar": "classic", "holographic_sleeves": True}, texture)
    assert any("holographic_sleeves" in w for w in result.warnings)


def test_try_on_places_the_garment_on_the_person_and_is_private(client, session, ai, h, monkeypatch, make_listing):
    use_pose(monkeypatch, _pose())
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    photo, _ = _photo(client, h)
    r = client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h, json={"body_photo_id": photo["id"]})
    assert r.status_code == 202 and r.json()["data"]["kind"] == "on_body"
    run_jobs(session)
    out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
    assert out["status"] == "completed" and out["method"] == "pose_landmark_composite_v1"
    assert "konseptual" in out["warnings"][0].lower()
    composite = Image.open(io.BytesIO(client.get(out["url"]).content))
    original = Image.open(io.BytesIO(ai.open(session.get(File, session.get(BodyPhoto, photo["id"]).file_id).storage_key)))
    assert composite.size == original.size and list(composite.getdata()) != list(original.getdata())
    file_id = session.get(Preview, out["id"]).file_id
    assert session.get(File, file_id).visibility == "private"
    assert client.get(f"{API}/files/{file_id}").status_code == 403


def test_try_on_needs_exactly_one_visible_person(client, session, ai, h, monkeypatch, make_listing):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    photo, _ = _photo(client, h)
    for pose, message in ((_pose(count=0), "tepat satu orang"), (_pose(count=2), "tepat satu orang"),
                          (_pose(shoulder_vis=0.1), "Bahu tidak terlihat")):
        use_pose(monkeypatch, pose)
        r = client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h, json={"body_photo_id": photo["id"]})
        run_jobs(session)
        out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
        assert out["status"] == "failed" and any(message in w for w in out["warnings"]) and out["url"] is None


def test_try_on_requires_own_photo(client, ai, h, make_user, auth_header, make_listing):
    cust = _create(client, h, make_listing())
    stranger = auth_header(make_user("stranger@example.com"))
    foreign, _ = _photo(client, stranger)
    r = client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h, json={"body_photo_id": foreign["id"]})
    assert r.status_code == 404


@pytest.mark.skipif(not REAL_MODEL.exists() or not ASSET.exists(), reason="pose model/test photo not installed")
def test_real_pose_try_on_on_a_public_domain_photo(client, session, ai, h, make_listing):
    get_pose_detector.cache_clear()
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    consent = _consent(client, h)
    photo = _upload(client, h, consent["id"], ASSET.read_bytes()).json()["data"]
    r = client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h, json={"body_photo_id": photo["id"]})
    run_jobs(session)
    out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
    assert out["status"] == "completed" and out["url"]
    img = Image.open(io.BytesIO(client.get(out["url"]).content))
    assert min(img.size) > 400


# ---------- seller-side visual analysis ----------

class FakeVLM:
    name = "fake-vlm"

    def __init__(self, raw=None, fail=None):
        self.raw, self.fail = raw, fail

    def analyze(self, image, content_type, candidates):
        if self.fail:
            raise RuntimeError(self.fail)
        return self.raw


RAW = {"technique": "ikat", "motif_category": "fauna", "dominant_colors": ["merah", "hitam", "emas", "biru"],
       "candidate_matches": ["Tenun Ikat Sumba", "Entri Fiktif"], "origin_guess": "Sumba",
       "origin_confidence": "medium", "is_traditional_woven_textile": True}


@pytest.fixture
def seller(session, make_partner, make_listing, ai):
    user, profile = make_partner("merchant", shop="Toko Analisis")
    listing = make_listing()
    listing.merchant_id = profile.id
    stored = create_file(session, ai, owner_id=user.id, kind="listing_photo", data=_fabric_png(),
                         content_type="image/png", visibility="public")
    session.add(ListingImage(listing_id=listing.id, file_id=stored.id))
    session.flush()
    return user, listing


def _analyze(client, headers, listing, vlm):
    app.dependency_overrides[get_vlm] = lambda: vlm
    return client.post(f"{API}/vision/analyze", headers=headers, json={"listing_id": str(listing.id)})


def test_analysis_is_normalised_and_stored_as_a_suggestion(client, session, seller, auth_header, entry):
    user, listing = seller
    r = _analyze(client, auth_header(user), listing, FakeVLM(RAW))
    assert r.status_code == 200, r.text
    result = r.json()["data"]["result"]
    assert result["technique"] == "ikat" and result["dominant_colors"] == ["merah", "hitam", "emas"]
    assert result["candidate_matches"] == ["Tenun Ikat Sumba"]  # names we do not know are dropped
    assert "Bukan sertifikasi" in r.json()["data"]["notice"]
    session.refresh(listing)
    vm = listing.visual_match
    assert vm["status"] == "suggestion" and vm["needs_merchant_review"] is True
    assert listing.curator_verified_origin is None and listing.merchant_claimed_origin is None


def test_unknown_values_become_unknown(client, session, seller, auth_header, entry):
    user, listing = seller
    raw = {**RAW, "technique": "teleportation", "motif_category": "??", "origin_confidence": "certain"}
    result = _analyze(client, auth_header(user), listing, FakeVLM(raw)).json()["data"]["result"]
    assert result["technique"] == "unknown" and result["motif_category"] == "unknown"
    assert result["origin_confidence"] == "low"


def test_no_provider_configured_returns_503_and_invents_nothing(client, session, seller, auth_header):
    user, listing = seller
    r = _analyze(client, auth_header(user), listing, None)
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"
    session.refresh(listing)
    assert listing.visual_match is None


def test_provider_failure_is_recorded_and_surfaced(client, session, seller, auth_header):
    from app.models import CvAnalysis

    user, listing = seller
    r = _analyze(client, auth_header(user), listing, FakeVLM(fail="HTTP 429: kredit habis"))
    assert r.status_code == 503 and "kredit habis" in r.json()["error"]["message"]
    row = session.scalar(select(CvAnalysis))
    assert row.status == "failed" and "kredit habis" in row.error
    session.refresh(listing)
    assert listing.visual_match is None


def test_only_the_listing_owner_can_analyze(client, session, seller, auth_header, make_partner, buyer):
    _user, listing = seller
    other, _ = make_partner("merchant", shop="Toko Lain")
    assert _analyze(client, auth_header(other), listing, FakeVLM(RAW)).status_code == 404
    assert _analyze(client, auth_header(buyer), listing, FakeVLM(RAW)).status_code == 403


def test_merchant_reviews_the_suggestion_without_touching_curator_data(client, session, seller, auth_header, entry):
    user, listing = seller
    h = auth_header(user)
    url = f"{API}/listings/{listing.id}/motif-review"
    assert client.patch(url, headers=h, json={"decision": "confirm"}).status_code == 422  # nothing to review yet
    _analyze(client, h, listing, FakeVLM(RAW))
    r = client.patch(url, headers=h, json={"decision": "confirm", "merchant_claimed_origin": "Tenun Sumba Timur"})
    origin = r.json()["data"]["origin"]
    assert origin["visual_match"]["review"]["decision"] == "confirm"
    assert origin["visual_match"]["needs_merchant_review"] is False
    assert origin["merchant_claimed_origin"] == "Tenun Sumba Timur"
    assert origin["curator_verified_origin"] is None  # three distinct fields stay distinct
    bad = client.patch(url, headers=h, json={"decision": "correct", "entry_id": "00000000-0000-0000-0000-000000000000"})
    assert bad.status_code == 422
    entry_row = session.scalar(select(GalleryEntry))
    ok = client.patch(url, headers=h, json={"decision": "correct", "entry_id": str(entry_row.id)})
    assert ok.json()["data"]["origin"]["visual_match"]["review"]["entry_id"] == str(entry_row.id)


def test_only_curators_can_verify_origin(client, session, seller, auth_header, make_user):
    user, listing = seller
    admin = auth_header(make_user("curator@example.com", roles=(("admin", "active"),)))
    url = f"{API}/admin/listings/{listing.id}/verify-origin"
    assert client.post(url, headers=auth_header(user), json={"text": "Sumba, NTT"}).status_code == 403
    r = client.post(url, headers=admin, json={"text": "Sumba, NTT (diverifikasi pengrajin)"})
    assert r.json()["data"]["origin"]["curator_verified_origin"].startswith("Sumba")
    assert r.json()["data"]["origin"]["merchant_claimed_origin"] is None
