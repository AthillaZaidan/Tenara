"""3D avatar preview: the buyer's body rebuilt from a measurement set, wearing the current design."""
import io
import math

import numpy as np
import pytest
from sqlalchemy import select
from test_ai import _add_texture, _fabric_png, ai, run_jobs  # noqa: F401
from test_customization import _apply, _create, buyer, entry, h, make_listing, synced  # noqa: F401

from app.ml.vision import avatar, body3d
from app.models import Job, Preview
from app.services import template_defs
from app.workers import handlers

API = "/api/v1"
DIMS = {"chest_circumference": 96, "waist_circumference": 84, "hip_circumference": 98, "shoulder_width": 40,
        "back_length": 42, "sleeve_length": 58, "neck_circumference": 38}
GLB = b"glTF\x02\x00\x00\x00fake"


@pytest.fixture
def fake_avatar(monkeypatch):
    """SMPL-X stand-in (no model files needed): records what the builder got."""
    calls = []

    def build(body, code, state, ease_cm, height_cm, values, texture):
        calls.append({"body": body, "code": code, "state": state, "ease": ease_cm, "height": height_cm,
                      "values": values, "texture": texture.size})
        return avatar.Avatar(glb=GLB, fitted={**values, "height": height_cm},
                             warnings=["avatar_mismatch:back_length: test"])

    monkeypatch.setattr(handlers, "_body_model", lambda gender: f"smplx-{gender}")
    monkeypatch.setattr(avatar, "build", build)
    return calls


def _mset(client, h, values=DIMS, height=170):
    r = client.post(f"{API}/measurement-sets", headers=h, json={"height_cm": height, "values": values})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _avatar(client, h, cust, mset, **extra):
    return client.post(f"{API}/customizations/{cust['id']}/avatar-previews", headers=h,
                       json={"measurement_set_id": mset["id"], **extra})


def test_avatar_is_built_from_the_measurements_and_served_as_glb(client, session, ai, h, make_listing, fake_avatar):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    mset = _mset(client, h)
    r = _avatar(client, h, cust, mset, gender="female")
    assert r.status_code == 202, r.text
    queued = r.json()["data"]
    assert queued["kind"] == "avatar_3d" and queued["status"] == "queued" and queued["url"] is None
    assert queued["measurement_set_id"] == mset["id"] and "bentuk badan" in queued["label"]
    run_jobs(session)
    done = client.get(f"{API}/previews/{queued['id']}", headers=h).json()["data"]
    assert done["status"] == "completed_with_warnings" and done["method"] == avatar.METHOD
    assert "tanpa foto" in done["warnings"][0] and any("avatar_mismatch" in w for w in done["warnings"])
    got = client.get(done["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "model/gltf-binary" and got.content == GLB
    call = fake_avatar[0]
    assert call["body"] == "smplx-female" and call["code"] == "T01" and call["height"] == 170
    assert call["values"]["chest_circumference"] == 96 and call["ease"] == 14
    assert call["texture"] == (512, 512)  # the listing's own fabric, mirrored 2x2


def test_changing_the_measurements_or_the_design_makes_the_avatar_stale(client, session, ai, h, make_listing,
                                                                        fake_avatar):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    mset = _mset(client, h)
    first = _avatar(client, h, cust, mset).json()["data"]
    run_jobs(session)
    r = client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                     json={"expected_revision": 1, "values": {"waist_circumference": 90}})
    assert r.status_code == 200, r.text
    stale = client.get(f"{API}/previews/{first['id']}", headers=h).json()["data"]
    assert stale["status"] == "stale" and stale["url"] is None
    second = _avatar(client, h, cust, r.json()["data"]).json()["data"]
    run_jobs(session)
    assert client.get(f"{API}/previews/{second['id']}", headers=h).json()["data"]["status"] != "stale"
    _apply(client, h, cust["id"], 1, changes={"collar": "none"})
    assert client.get(f"{API}/previews/{second['id']}", headers=h).json()["data"]["status"] == "stale"


def test_measurements_edited_while_queued_fail_the_job_honestly(client, session, ai, h, make_listing, fake_avatar):
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    mset = _mset(client, h)
    _avatar(client, h, cust, mset)
    client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                 json={"expected_revision": 1, "values": {"waist_circumference": 90}})
    run_jobs(session)
    job = session.scalar(select(Job).where(Job.kind == "preview.avatar_3d"))
    assert job.status == "failed" and "berubah" in job.error and not fake_avatar


def test_avatar_needs_height_values_an_own_set_and_a_known_body_model(client, h, make_listing, make_user,
                                                                      auth_header):
    cust = _create(client, h, make_listing())
    no_height = client.post(f"{API}/measurement-sets", headers=h, json={"values": DIMS}).json()["data"]
    assert _avatar(client, h, cust, no_height).json()["error"]["field"] == "measurement_set_id"
    empty = _mset(client, h, values={})
    assert "minimal satu" in _avatar(client, h, cust, empty).json()["error"]["message"]
    assert _avatar(client, h, cust, _mset(client, h), gender="robot").status_code == 422
    other = auth_header(make_user("someone@example.com"))
    assert _avatar(client, h, cust, _mset(client, other)).status_code == 404


def test_without_smplx_installed_the_avatar_fails_and_says_why(client, session, ai, h, make_listing, monkeypatch):
    monkeypatch.setattr(handlers, "_body_model", lambda gender: None)
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    preview = _avatar(client, h, cust, _mset(client, h)).json()["data"]
    run_jobs(session)
    out = client.get(f"{API}/previews/{preview['id']}", headers=h).json()["data"]
    assert out["status"] == "failed" and any("SMPL-X" in w for w in out["warnings"])
    assert session.get(Preview, preview["id"]).file_id is None


# ---------- geometry, without the body model ----------

def test_ray_radii_reach_the_edge_of_a_square_in_every_direction():
    square = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])
    r = avatar._ray_radii(square, np.zeros(2), np.array([0.0, math.pi / 4, math.pi / 2, math.pi]))
    assert r == pytest.approx([1.0, math.sqrt(2), 1.0, 1.0])


def test_area_centroid_ignores_where_the_corners_fall():
    # a square with extra corners bunched on one side: the corner mean moves, the area centroid does not
    poly = np.array([[0, 0], [2, 0], [2, 0.1], [2, 0.2], [2, 0.3], [2, 2], [0, 2]], dtype=float)
    assert avatar._centroid(poly) == pytest.approx([1.0, 1.0])
    assert poly.mean(axis=0)[0] > 1.1


def test_cloth_hangs_from_the_chest_instead_of_following_the_waist():
    radii = np.array([[0.14] * 3, [0.12] * 3, [0.13] * 3, [0.15] * 3])  # hem .. chest (index 3)
    hung = avatar._drape(radii, 3, -1, taper=0.99)
    assert hung[1, 0] > 0.14 and hung[2, 0] > 0.14  # the waist hollow is bridged
    assert hung[0, 0] < hung[3, 0]  # yet it may narrow slowly towards the hem


def test_fabric_texture_is_mirrored_so_repeats_have_no_seam():
    tex = np.asarray(avatar.fabric_texture(_fabric_png(), size=64))
    assert tex.shape == (128, 128, 3)
    assert np.array_equal(tex[:, 63], tex[:, 64]) and np.array_equal(tex[63], tex[64])
    assert np.array_equal(tex[:, 0], tex[:, -1]) and np.array_equal(tex[0], tex[-1])


# ---------- the real model (skipped where SMPL-X is not installed) ----------

@pytest.mark.skipif(body3d.get_body_model("neutral") is None, reason="SMPL-X model files not installed")
@pytest.mark.parametrize("code", sorted(template_defs.DEFINITIONS))
def test_real_avatar_matches_the_measurements_and_exports_a_glb(code):
    import trimesh

    body = body3d.get_body_model("neutral")
    defn = template_defs.definition(code)
    state = template_defs.defaults(defn)
    texture = avatar.fabric_texture(_fabric_png())
    out = avatar.build(body, code, state, defn["material_rules"]["ease_cm"], 170.0, dict(DIMS), texture)
    assert out.glb[:4] == b"glTF"
    for key in ("chest_circumference", "waist_circumference", "hip_circumference"):
        assert out.fitted[key] == pytest.approx(DIMS[key], abs=3.0)
    assert out.fitted["height"] == pytest.approx(170.0, abs=1.5)
    scene = trimesh.load(io.BytesIO(out.glb), file_type="glb")
    names = set(scene.geometry)
    assert "body" in names and any(n.startswith("garment_0") for n in names)
    assert any(n.startswith("garment_1") for n in names) == (code != "T03")  # the vest has no sleeves
