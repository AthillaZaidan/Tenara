"""Measuring from a front and a side photo with a fitted SMPL-X body."""
import math

import numpy as np
import pytest
from sqlalchemy import select
from test_ai import _consent, _photo, _pose, _upload, _values, ai, run_jobs, use_pose  # noqa: F401
from test_customization import buyer, entry, h, make_listing  # noqa: F401

from app.ml.vision import body3d
from app.models import Job, MeasurementSet
from app.workers import handlers

API = "/api/v1"
VALUES = {"neck_circumference": 40.6, "chest_circumference": 111.8, "waist_circumference": 102.5,
          "hip_circumference": 111.1, "shoulder_width": 35.6, "sleeve_length": 51.3, "back_length": 38.7,
          "height": 168.0}
VISUAL = {"front": {"frame": [600, 900], "rings": [{"key": "chest_circumference", "cx": 300, "cy": 300, "rx": 80, "ry": 9.6}],
                    "lines": [{"key": "shoulder_width", "points": [[220, 250], [380, 250]]}]},
          "side": {"frame": [600, 900], "rings": [], "lines": [{"key": "back_length", "points": [[330, 250], [330, 420]]}]}}


@pytest.fixture
def fake_3d(monkeypatch):
    """SMPL-X stand-in: records what it got and returns fixed measurements (no model files needed)."""
    calls = []

    def estimate(body, detector, front, side, height_cm, steps=300):
        calls.append({"body": body, "sizes": (front.size, side.size), "height": height_cm})
        return {"problems": [], "values": dict(VALUES), "visual": VISUAL, "fit_loss": 0.2}

    monkeypatch.setattr(handlers, "_body_model", lambda gender: f"smplx-{gender}")
    monkeypatch.setattr(body3d, "estimate_two_views", estimate)
    return calls


def _two(client, h, monkeypatch, gender="male", height=168):
    use_pose(monkeypatch, _pose())
    front, consent = _photo(client, h)
    side = _upload(client, h, consent["id"]).json()["data"]
    r = client.post(f"{API}/body-measurements/estimate", headers=h, json={
        "body_photo_id": front["id"], "side_photo_id": side["id"], "height_cm": height, "gender": gender})
    assert r.status_code == 202, r.text
    return front, side, r.json()["data"]["job_id"]


def test_front_and_side_photos_give_all_seven_dimensions_and_where_to_draw_them(client, session, ai, h, monkeypatch,
                                                                              fake_3d):
    front, side, job_id = _two(client, h, monkeypatch)
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["status"] == "completed_with_warnings" and out["output"]["method"] == "smplx_two_view"
    assert fake_3d[0]["body"] == "smplx-male" and fake_3d[0]["height"] == 168
    v = _values(out)
    assert v["chest_circumference"]["value_cm"] == pytest.approx(111.8)
    assert all(x["source"] == "estimated" and x["quality_flag"] == "review_required" for x in v.values())
    assert out["model_version"].startswith(body3d.MODEL_VERSION)
    assert any("loose_clothing" in w for w in out["output"]["warnings"])
    # geometry only (no new image of the body is stored), with private links to the owner's own photos
    vis = out["visual"]
    assert vis["front"]["photo_id"] == front["id"] and vis["side"]["photo_id"] == side["id"]
    assert vis["front"]["photo_url"].startswith("/api/v1/files/") and vis["front"]["rings"][0]["key"] == "chest_circumference"


def test_deleting_the_photos_removes_the_drawing_but_keeps_the_measurements(client, session, ai, h, monkeypatch,
                                                                           fake_3d):
    front, side, job_id = _two(client, h, monkeypatch)
    run_jobs(session)
    assert client.delete(f"{API}/body-photos/{front['id']}", headers=h).status_code == 200
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert set(out["visual"]) == {"side"}
    client.delete(f"{API}/body-photos/{side['id']}", headers=h)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["visual"] is None and out["measurement_set"]["values"]


def test_implausible_values_are_left_for_the_buyer(client, session, ai, h, monkeypatch, fake_3d):
    VALUES_BAD = {**VALUES, "neck_circumference": 99.0}
    monkeypatch.setattr(body3d, "estimate_two_views", lambda *a, **k: {
        "problems": [], "values": VALUES_BAD, "visual": VISUAL, "fit_loss": 1.0})
    _, _, job_id = _two(client, h, monkeypatch)
    run_jobs(session)
    v = _values(client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"])
    assert v["neck_circumference"]["value_cm"] is None and v["neck_circumference"]["quality_flag"] == "implausible"


def test_photo_problems_fail_the_job_with_the_reasons(client, session, ai, h, monkeypatch, fake_3d):
    monkeypatch.setattr(body3d, "estimate_two_views", lambda *a, **k: {
        "problems": ["Foto depan: kaki tidak terlihat jelas.", "Foto samping: badan terpotong di tepi foto."]})
    _, _, job_id = _two(client, h, monkeypatch)
    run_jobs(session)
    session.expire_all()
    job = session.get(Job, job_id)
    assert job.status == "failed" and "kaki tidak terlihat" in job.error and "terpotong" in job.error
    assert job.attempts == 1 and session.scalar(select(MeasurementSet)) is None


def test_without_smplx_installed_the_front_photo_is_still_used_and_says_so(client, session, ai, h, monkeypatch):
    monkeypatch.setattr(handlers, "_body_model", lambda gender: None)
    _, _, job_id = _two(client, h, monkeypatch)
    run_jobs(session)
    out = client.get(f"{API}/body-measurements/{job_id}", headers=h).json()["data"]
    assert out["output"]["method"] == "pose_front_only"
    assert any("smplx_unavailable" in w for w in out["output"]["warnings"])
    assert _values(out)["chest_circumference"]["source"] == "manual_required"


def test_side_photo_must_be_another_photo_of_the_same_owner(client, ai, h, monkeypatch, make_user, auth_header):
    use_pose(monkeypatch, _pose())
    front, _ = _photo(client, h)
    same = client.post(f"{API}/body-measurements/estimate", headers=h, json={
        "body_photo_id": front["id"], "side_photo_id": front["id"], "height_cm": 168})
    assert same.status_code == 422
    other_h = auth_header(make_user("other3d@example.com"))
    theirs, _ = _photo(client, other_h)
    r = client.post(f"{API}/body-measurements/estimate", headers=h, json={
        "body_photo_id": front["id"], "side_photo_id": theirs["id"], "height_cm": 168})
    assert r.status_code == 404
    assert client.post(f"{API}/body-measurements/estimate", headers=h, json={
        "body_photo_id": front["id"], "side_photo_id": theirs["id"], "height_cm": 168, "gender": "x"}).status_code == 422


# ---------- geometry helpers (no model files) ----------

def test_hull_perimeter_of_a_square_with_inner_points():
    pts = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5], [0.2, 0.7]])
    assert body3d._hull_perimeter(pts) == pytest.approx(4.0)


def test_mask_is_cut_at_the_heels_so_floor_reflections_and_toes_do_not_stretch_the_figure():
    mask = np.zeros((100, 20), dtype=bool)
    mask[10:100, 8:12] = True  # figure runs into the bottom edge (reflection)
    lm = {"l_heel": (9.0, 80.0, 0.9), "r_heel": (11.0, 81.0, 0.9), "l_foot_index": (9.0, 99.0, 0.9)}
    trimmed = body3d.trim_below_feet(mask, lm)
    assert np.nonzero(trimmed.any(axis=1))[0].max() == 81  # the heel row stays, the reflection below goes
    assert body3d.trim_below_feet(mask, {}).sum() == mask.sum()  # nothing to go by: left as is


def _view(kind, mask=None, **vis):
    mask = np.zeros((100, 60), dtype=bool) if mask is None else mask
    lm = {n: (30.0, 50.0, vis.get(n, 1.0)) for n in ("l_shoulder", "r_shoulder", "l_hip", "r_hip", "l_ankle", "r_ankle")}
    return body3d.View(kind=kind, mask=mask, landmarks=lm)


def test_photo_checks_explain_what_to_retake():
    ok_mask = np.zeros((100, 60), dtype=bool)
    ok_mask[5:95, 20:40] = True
    assert body3d.check_views([_view("front", ok_mask), _view("side", ok_mask)]) == []
    cut = ok_mask.copy()
    cut[95:] = True
    problems = body3d.check_views([_view("front", cut, l_ankle=0.1, r_ankle=0.2), _view("side", ok_mask)])
    assert any("kaki tidak terlihat" in p for p in problems) and any("terpotong" in p for p in problems)
    assert any("satu foto depan" in p for p in body3d.check_views([_view("front", ok_mask)]))


def test_side_photo_facing_is_read_from_the_nose():
    v = _view("side")
    v.landmarks["nose"] = (45.0, 20.0, 1.0)
    assert body3d.side_yaw(v) == pytest.approx(math.pi / 2)
    v.landmarks["nose"] = (15.0, 20.0, 1.0)
    assert body3d.side_yaw(v) == pytest.approx(-math.pi / 2)


def test_rows_next_to_an_arm_are_skipped_as_ambiguous():
    mask = np.zeros((10, 40), dtype=bool)
    mask[5, 10:20] = True  # body run
    mask[5, 22:24] = True  # arm 2 px away
    assert body3d._row_extents(mask, 5, 15, margin=4) is None
    assert body3d._row_extents(mask, 5, 15, margin=1) == (10.0, 19.0)


# ---------- the real model (skipped where SMPL-X is not installed) ----------

@pytest.mark.skipif(body3d.get_body_model("neutral") is None, reason="SMPL-X model files not installed")
def test_fitting_recovers_a_known_synthetic_body_within_a_few_centimetres():
    from PIL import Image, ImageDraw

    body = body3d.get_body_model("neutral")
    torch = body.torch
    betas = np.zeros(body3d.NUM_BETAS)
    betas[:4] = [0.8, -0.6, 0.5, 0.3]
    truth = body3d.measure(body, betas)
    names = {v: k for k, v in body3d.MP_TO_SMPLX.items()}
    views = []
    for kind, arm, yaw in (("front", 0.9, 0.0), ("side", 1.35, math.pi / 2)):
        pose = torch.zeros(1, 63)
        pose[0, (body3d.L_SHOULDER - 1) * 3 + 2], pose[0, (body3d.R_SHOULDER - 1) * 3 + 2] = -arm, arm
        with torch.no_grad():
            out = body.model(betas=torch.tensor(betas, dtype=torch.float32)[None], body_pose=pose,
                             global_orient=torch.tensor([[0.0, yaw, 0.0]]))
        v, j = out.vertices[0].numpy(), out.joints[0].numpy()
        s, cx, cy = 520.0, 350 - 520.0 * v[:, 0].mean(), 60 + 520.0 * v[:, 1].max()
        uv = np.stack([s * v[:, 0] + cx, -s * v[:, 1] + cy], 1)
        img = Image.new("L", (700, 1100), 0)
        draw = ImageDraw.Draw(img)
        for f in body.faces:
            draw.polygon([tuple(uv[i]) for i in f], fill=255)
        lm = {names[i]: (float(s * j[i, 0] + cx), float(-s * j[i, 1] + cy), 1.0) for i in names}
        views.append(body3d.View(kind=kind, mask=np.asarray(img) > 0, landmarks=lm))
    fitted, _ = body3d.fit(body, views, truth["height"], steps=300)
    got = body3d.measure(body, fitted)
    for key in ("chest_circumference", "waist_circumference", "hip_circumference", "neck_circumference"):
        assert abs(got[key] - truth[key]) < 4.0, (key, got[key], truth[key])

