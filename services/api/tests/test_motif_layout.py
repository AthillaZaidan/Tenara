"""Motif layout: a fabric map of the listing photo, prompts that place its parts on the garment, and the
3D avatar that shows the actual fabric there."""
import io

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select
from test_ai import _add_texture, _fabric_png, ai, run_jobs  # noqa: F401
from test_customization import _apply, _create, buyer, entry, h, make_listing, synced  # noqa: F401

from app.ml.text.prompt_interpreter import RuleBasedInterpreter
from app.ml.vision import avatar, body3d, fabric_map
from app.models import FabricMap, MerchantProfile, User
from app.services import template_defs
from app.workers import handlers

API = "/api/v1"
# what Gemma 4 26B returned for the KITLV ikat photo on 2026-11-14 (web/public/img/ikat-1.jpg)
RAW = {"zones": [{"kind": "kepala_kain", "box": [0, 0, 1000, 270]}, {"kind": "badan", "box": [0, 270, 1000, 770]},
                 {"kind": "pinggiran", "box": [0, 770, 1000, 800]}, {"kind": "rumbai", "box": [40, 800, 940, 1000]},
                 {"kind": "latar_luar", "box": [0, 0, 10, 10]}],
       "motifs": [{"name": "manusia", "box": [70, 360, 580, 580], "repeats": 4},
                  {"name": "Burung-burung", "box": [50, 280, 950, 370], "repeats": 10},
                  {"name": "belah ketupat", "box": [350, 10, 650, 250], "repeats": 3},
                  {"name": "garis", "box": [10, 10, 12, 900]}]}
PROMPT = "motif manusianya taruh di dada, burung-burung di bawahan, kepala kainnya jangan dipakai"


@pytest.fixture
def fake_map(monkeypatch):
    calls = []

    def locate(image, content_type):
        calls.append(content_type)
        return RAW

    monkeypatch.setattr(fabric_map, "locate", locate)
    monkeypatch.setattr(fabric_map, "available", lambda: True)
    return calls


def _merchant_header(session, listing, auth_header):
    return auth_header(session.get(User, session.get(MerchantProfile, listing.merchant_id).user_id))


def _mapped(client, session, h, make_listing, code="T05"):
    listing = make_listing()
    cust = _create(client, h, listing, code)
    _add_texture(session, make_listing, cust)
    r = client.post(f"{API}/listings/{listing.id}/fabric-map", headers=h)
    assert r.status_code == 202, r.text
    run_jobs(session)
    return listing, cust


def _regions():
    return fabric_map.normalise(RAW)


# ---------- the fabric map ----------

def test_normalise_keeps_known_zones_and_named_motifs_with_clean_boxes():
    regions = _regions()
    labels = [(r["id"], r["label"]) for r in regions]
    assert labels == [("z1", "kepala kain"), ("z2", "badan kain"), ("z3", "pinggiran"), ("z4", "rumbai"),
                      ("m1", "manusia"), ("m2", "burung"), ("m3", "belah ketupat")]  # no background, no sliver
    assert regions[4]["box"] == [0.07, 0.36, 0.58, 0.58] and regions[4]["repeats"] == 4


def test_fabric_map_is_requested_once_estimated_and_public(client, session, ai, h, make_listing, fake_map):
    listing, _ = _mapped(client, session, h, make_listing)
    out = client.get(f"{API}/listings/{listing.id}/fabric-map").json()["data"]
    assert out["status"] == "estimated" and "perkiraan" in out["label"].lower()
    assert [r["label"] for r in out["regions"]][:2] == ["kepala kain", "badan kain"]
    again = client.post(f"{API}/listings/{listing.id}/fabric-map", headers=h).json()["data"]
    assert again["id"] == out["id"] and len(fake_map) == 1  # one model call per photo
    assert client.post(f"{API}/listings/{listing.id}/fabric-map").status_code == 401


def test_without_a_vision_model_the_map_is_unavailable(client, session, h, make_listing, monkeypatch):
    monkeypatch.setattr(fabric_map, "available", lambda: False)
    listing = make_listing()
    cust = _create(client, h, listing)
    _add_texture(session, make_listing, cust)
    r = client.post(f"{API}/listings/{listing.id}/fabric-map", headers=h)
    assert r.status_code == 503 and session.scalar(select(FabricMap)) is None


def test_merchant_confirms_or_corrects_the_map(client, session, ai, h, make_listing, fake_map, auth_header):
    listing, _ = _mapped(client, session, h, make_listing)
    url = f"{API}/merchant/listings/{listing.id}/fabric-map"
    assert client.put(url, headers=h, json={"expected_revision": 1}).status_code in (403, 404)
    mh = _merchant_header(session, listing, auth_header)
    bad = client.put(url, headers=mh, json={"expected_revision": 1, "regions": [
        {"id": "m1", "kind": "motif", "label": "manusia", "box": [0.5, 0.1, 0.2, 0.3]}]})
    assert bad.status_code == 422 and bad.json()["error"]["field"] == "regions.0.box"
    fixed = client.put(url, headers=mh, json={"expected_revision": 1, "regions": [
        {"id": "z2", "kind": "zone", "label": "badan kain", "box": [0.05, 0.27, 0.95, 0.77]},
        {"id": "m1", "kind": "motif", "label": "Manusia", "box": [0.06, 0.34, 0.33, 0.6], "repeats": 4}]})
    out = fixed.json()["data"]
    assert out["status"] == "confirmed" and out["revision"] == 2 and "Dikonfirmasi" in out["label"]
    assert out["regions"][1]["label"] == "manusia"
    assert client.put(url, headers=mh, json={"expected_revision": 1}).status_code == 409


# ---------- prompt -> layout ----------

def _interpret(prompt, code="T05", state=None):
    defn = template_defs.definition(code)
    return RuleBasedInterpreter().interpret(prompt, defn, state or template_defs.defaults(defn), _usable())


def _usable():
    return [r for r in _regions() if r["label"] != "rumbai"]


def test_the_example_prompt_becomes_one_layout_change():
    out = _interpret(PROMPT)
    assert out["unsupported"] == [] and out["clarifications"] == []
    assert out["changes"] == [{"field": "motif_layout",
                               "value": {"panels": {"front": "m1", "hem": "m2"}, "avoid": ["z1"]}}]


def test_a_motif_not_on_the_fabric_is_refused_with_what_is_there():
    out = _interpret("motif kuda di punggung")
    assert out["changes"] == [] and "kuda" in out["unsupported"][0]["reason"]
    assert "manusia" in out["unsupported"][0]["alternatives"]


def test_a_motif_without_a_garment_part_asks_where():
    out = _interpret("pakai burung")
    clar = out["clarifications"][0]
    assert clar["field"] == "motif_layout" and clar["region"] == "m2" and "sleeves" in clar["choices"]


def test_a_vest_has_no_sleeves_to_put_a_motif_on():
    out = _interpret("manusia di lengan", code="T03")
    assert out["changes"] == [] and "sleeves" in out["unsupported"][0]["reason"]


def test_ordinary_motif_placement_still_works_without_a_map():
    defn = template_defs.definition("T05")
    out = RuleBasedInterpreter().interpret("motif di pinggiran bawah saja", defn, template_defs.defaults(defn), [])
    assert out["changes"] == [{"field": "motif_placement", "value": "hem_border"}]


def test_prompt_layout_is_stored_as_snapshots_in_the_design(client, session, ai, h, make_listing, fake_map):
    _, cust = _mapped(client, session, h, make_listing)
    r = client.post(f"{API}/customizations/{cust['id']}/prompt-changes", headers=h,
                    json={"expected_design_revision": 1, "prompt": PROMPT})
    assert r.status_code == 200, r.text
    proposal = r.json()["data"]
    change = proposal["changes"][0]
    assert change["field"] == "motif_layout" and change["value"]["panels"]["front"]["label"] == "manusia"
    _apply(client, h, cust["id"], 1, proposal_id=proposal["proposal_id"])
    state = client.get(f"{API}/customizations/{cust['id']}", headers=h).json()["data"]["state"]
    layout = state["motif_layout"]
    assert layout["panels"]["hem"] == {"region": "m2", "kind": "motif", "label": "burung", "box": [0.05, 0.28, 0.95, 0.37]}
    assert [a["label"] for a in layout["avoid"]] == ["kepala kain"]


def test_clarified_garment_part_is_applied(client, session, ai, h, make_listing, fake_map):
    _, cust = _mapped(client, session, h, make_listing)
    proposal = client.post(f"{API}/customizations/{cust['id']}/prompt-changes", headers=h,
                           json={"expected_design_revision": 1, "prompt": "pakai burung"}).json()["data"]
    clar = proposal["clarifications"][0]
    _apply(client, h, cust["id"], 1, proposal_id=proposal["proposal_id"], resolutions={clar["id"]: "back"})
    state = client.get(f"{API}/customizations/{cust['id']}", headers=h).json()["data"]["state"]
    assert state["motif_layout"]["panels"]["back"]["label"] == "burung"


def test_manual_layout_by_region_id_and_unknown_ids(client, session, ai, h, make_listing, fake_map):
    _, cust = _mapped(client, session, h, make_listing)
    bad = client.post(f"{API}/customizations/{cust['id']}/revisions", headers=h, json={
        "expected_design_revision": 1, "changes": {"motif_layout": {"panels": {"front": "m9"}}}})
    assert bad.status_code == 422 and "m9" in bad.json()["error"]["message"]
    clash = client.post(f"{API}/customizations/{cust['id']}/revisions", headers=h, json={
        "expected_design_revision": 1, "changes": {"motif_layout": {"panels": {"front": "m1"}, "avoid": ["m1"]}}})
    assert clash.status_code == 422
    ok = client.post(f"{API}/customizations/{cust['id']}/revisions", headers=h, json={
        "expected_design_revision": 1, "changes": {"motif_layout": {"panels": {"sleeves": "m3"}}}})
    assert ok.status_code in (200, 201), ok.text


# ---------- the avatar shows it ----------

def test_avatar_cuts_the_named_parts_of_the_fabric_photo(client, session, ai, h, make_listing, fake_map, monkeypatch):
    calls = []

    def build(body, code, state, ease_cm, height_cm, values, texture, panels=None, default=None):
        calls.append({"panels": {p: (t.label, t.image.size) for p, t in (panels or {}).items()},
                      "default": default.label if default else None})
        return avatar.Avatar(glb=b"glTF", fitted={**values, "height": height_cm})

    monkeypatch.setattr(handlers, "_body_model", lambda gender: "smplx")
    monkeypatch.setattr(avatar, "build", build)
    _, cust = _mapped(client, session, h, make_listing)
    proposal = client.post(f"{API}/customizations/{cust['id']}/prompt-changes", headers=h,
                           json={"expected_design_revision": 1, "prompt": PROMPT}).json()["data"]
    _apply(client, h, cust["id"], 1, proposal_id=proposal["proposal_id"])
    mset = client.post(f"{API}/measurement-sets", headers=h,
                       json={"height_cm": 165, "values": {"chest_circumference": 92}}).json()["data"]
    preview = client.post(f"{API}/customizations/{cust['id']}/avatar-previews", headers=h,
                          json={"measurement_set_id": mset["id"]}).json()["data"]
    run_jobs(session)
    done = client.get(f"{API}/previews/{preview['id']}", headers=h).json()["data"]
    assert done["status"] == "completed_with_warnings", done
    assert set(calls[0]["panels"]) == {"front", "hem"} and calls[0]["panels"]["front"][0] == "manusia"
    assert calls[0]["default"] == "badan kain"  # the head panel is avoided, so the rest is the body of the cloth
    text = " ".join(done["warnings"])
    assert "badan depan: manusia" in text and "perkiraan AI" in text
    assert "scale_assumed" not in text  # the test listing has a usable width


def test_region_texture_keeps_real_size_and_trims_a_plain_mount():
    photo = Image.new("RGB", (400, 200), (250, 250, 250))
    stripes = Image.open(io.BytesIO(_fabric_png())).convert("RGB").resize((300, 200))
    photo.paste(stripes, (100, 0))  # a 100 px plain mount on the left, like the archive photo
    tex = avatar.region_texture(photo, [0.0, 0.0, 1.0, 1.0], cm_per_px=0.5, label="badan kain")
    assert abs(tex.tile_w_m - 2 * 300 * 0.5 / 100) < 0.05 and abs(tex.tile_h_m - 1.0) < 0.05
    left, right = np.asarray(tex.image)[:, :2], np.asarray(tex.image)[:, -2:]
    assert np.array_equal(left, right[:, ::-1])  # mirrored pair: repeats meet without a seam


def test_photo_scale_uses_the_widest_zone_or_assumes_100_cm():
    assert avatar.photo_scale(1000, [0.5, 0.8], 120) == (120 / 800, False)
    assert avatar.photo_scale(1000, [], None) == (100 / 900, True)


@pytest.mark.skipif(body3d.get_body_model("neutral") is None, reason="SMPL-X model files not installed")
def test_real_avatar_has_its_own_fabric_on_the_named_parts():
    import trimesh

    photo = Image.open(io.BytesIO(_fabric_png()))
    panels = {"front": avatar.region_texture(photo, [0.1, 0.1, 0.6, 0.5], 0.4, "manusia"),
              "hem": avatar.region_texture(photo, [0.0, 0.7, 1.0, 0.8], 0.4, "burung")}
    defn = template_defs.definition("T05")
    out = avatar.build(body3d.get_body_model("neutral"), "T05", template_defs.defaults(defn),
                       defn["material_rules"]["ease_cm"], 170.0, {"chest_circumference": 96},
                       avatar.fabric_texture(_fabric_png()), panels=panels)
    names = set(trimesh.load(io.BytesIO(out.glb), file_type="glb").geometry)
    assert {"garment_0_panel_front", "garment_0_panel_hem", "garment_0_motif"} <= names
    assert not any(n.startswith("garment_1_panel") for n in names)  # sleeves keep the default fabric

