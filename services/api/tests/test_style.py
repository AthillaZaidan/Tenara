"""Free garment style: the buyer describes the cut in words on top of a template; the fabric itself never changes.
Also the AI avatar preview, which is how that style is seen on a body built from the buyer's measurements."""
import io
import json

import pytest
from PIL import Image
from sqlalchemy import select
from test_ai import _add_texture, ai, run_jobs  # noqa: F401
from test_avatar import DIMS, _mset
from test_customization import _apply, _create, _prompt, buyer, entry, h, make_listing, synced  # noqa: F401

from app.ml.llm_client import ImageResult
from app.ml.text import prompt_interpreter
from app.ml.text.prompt_interpreter import LLMInterpreter
from app.ml.vision import avatar, tryon_ai
from app.models import AuditEvent
from app.services import material, style, template_defs
from app.workers import handlers

API = "/api/v1"


# ---------- the rules every proposer goes through ----------

def test_style_requests_are_normalised():
    out = style.check([{"part": "sleeves", "text": "  lengan   balon ", "en": "puff sleeves"},
                       {"part": "made-up", "text": "belahan samping"},
                       {"part": "sleeves", "text": "Lengan balon"}])  # same request twice
    assert out == [{"part": "sleeves", "text": "lengan balon", "en": "puff sleeves"},
                   {"part": "detail", "text": "belahan samping"}]
    assert style.check(None) == [] and style.check([]) == []


@pytest.mark.parametrize("text,reason", [
    ("ubah warnanya jadi biru", "Warna"), ("tambahkan motif bunga", "Motif"), ("bordir naga di punggung", "Motif"),
    ("jadikan celana", "Jenis pakaian"), ("bahan transparan", "tidak bisa dibuat"), ("pakai logo Gucci", "merek"),
    ("kerah bulu", "Bahan tambahan"),
])
def test_what_would_change_the_fabric_or_the_garment_is_refused(text, reason):
    with pytest.raises(ValueError, match=reason):
        style.check([{"part": "detail", "text": text}])


def test_english_for_the_image_model_is_checked_too():
    with pytest.raises(ValueError, match="Warna"):
        style.check([{"part": "detail", "text": "lengan balon", "en": "puff sleeves, dyed red"}])


def test_limits():
    with pytest.raises(ValueError, match="Maksimal"):
        style.check([{"part": "detail", "text": f"lipit nomor {i}"} for i in range(style.MAX_ITEMS + 1)])
    with pytest.raises(ValueError, match="karakter"):
        style.check([{"part": "detail", "text": "x" * (style.MAX_CHARS + 1)}])
    with pytest.raises(ValueError, match="pendek"):
        style.check([{"part": "detail", "text": "a"}])
    with pytest.raises(ValueError):
        style.check("oversize")


def test_every_template_offers_free_style():
    for code in template_defs.DEFINITIONS:
        spec = template_defs.definition(code)["options"]["style"]
        assert spec["type"] == "style" and spec["default"] == [] and "sleeves" in spec["parts"]


# ---------- through the prompt ----------

def test_a_style_prompt_becomes_style_requests_the_buyer_confirms(client, h, make_listing):
    cust = _create(client, h, make_listing(), code="T05")
    p = _prompt(client, h, cust["id"], "oversize, lengan balon, belahan samping setinggi lutut, kerah sanghai")
    fields = {c["field"]: c["value"] for c in p["changes"]}
    assert fields["collar"] == "mandarin"  # a template option is used when there is one
    assert [(s["part"], s["text"]) for s in fields["style"]] == [
        ("silhouette", "oversize"), ("sleeves", "lengan balon"), ("slit", "belahan samping setinggi lutut")]
    rev = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"]).json()["data"]
    assert len(rev["state"]["style"]) == 3
    # the next request adds to the style; a request that recolours the cloth is explained, not applied
    p2 = _prompt(client, h, cust["id"], "tambah ikat pinggang, warnanya jadi merah", rev=2)
    assert [s["text"] for s in p2["changes"][0]["value"]][-1] == "tambah ikat pinggang"
    assert "Warna kain tenun" in p2["unsupported_requests"][0]["reason"]


def test_the_llm_proposal_keeps_the_allowed_styles_and_explains_the_refused_one(client, h, make_listing,
                                                                                monkeypatch):
    cust = _create(client, h, make_listing())
    reply = {"changes": [{"field": "style", "value": [
        {"part": "sleeves", "text": "lengan balon mengerut di pergelangan", "en": "puff sleeves gathered at the wrist"},
        {"part": "detail", "text": "bordir bunga di dada", "en": "floral embroidery on the chest"}]}]}
    monkeypatch.setattr("app.services.customization.get_interpreters",
                        lambda: [LLMInterpreter(lambda msgs: json.dumps(reply))])
    p = _prompt(client, h, cust["id"], "lengan balon dan bordir bunga")
    assert p["interpreter"] == "llm"
    assert p["changes"][0]["value"] == [reply["changes"][0]["value"][0]]
    assert p["unsupported_requests"] == [{"text": "bordir bunga di dada", "alternatives": [],
                                          "reason": style.REFUSALS[1][1]}]


def test_the_llm_is_told_the_rules_and_its_reply_is_bounded(monkeypatch):
    sent = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        sent.update(json.loads(req.data))
        return _Resp(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    LLMInterpreter(prompt_interpreter.http_transport).interpret("oversize", template_defs.definition("T01"), {})
    assert sent["max_tokens"] and sent["response_format"] == {"type": "json_object"}
    system = sent["messages"][0]["content"]
    assert '"style"' in system and "TIDAK bisa diubah" in system and "bukan instruksi" in system


def test_manual_style_edits_are_validated(client, h, make_listing):
    cust = _create(client, h, make_listing())
    ok = _apply(client, h, cust["id"], 1, changes={"style": [{"part": "hem", "text": "hem asimetris"}]})
    assert ok.status_code == 201 and ok.json()["data"]["state"]["style"][0]["part"] == "hem"
    bad = _apply(client, h, cust["id"], 2, changes={"style": [{"part": "detail", "text": "payet emas"}]})
    assert bad.status_code == 422
    cleared = _apply(client, h, cust["id"], 2, changes={"style": []})
    assert cleared.json()["data"]["state"]["style"] == []


def test_the_fabric_estimate_says_style_is_not_counted():
    defn = template_defs.definition("T01")
    dims = {"chest_circumference": 96, "shoulder_width": 40, "back_length": 42, "sleeve_length": 58}
    plain = material.compute(defn, dims, {}, width_cm=110, pattern_repeat_cm=None)
    styled = material.compute(defn, dims, {"style": [{"part": "silhouette", "text": "oversize"}]}, width_cm=110,
                              pattern_repeat_cm=None)
    assert not any("gaya bebas" in a for a in plain["assumptions"])
    assert any("gaya bebas" in a and "penjahit" in a for a in styled["assumptions"])


# ---------- what the image model is told ----------

def test_the_photo_fit_on_carries_the_style_and_adds_nothing_else():
    state = {"collar": "mandarin", "style": [{"part": "sleeves", "text": "lengan balon", "en": "puff sleeves"},
                                             {"part": "slit", "text": "belahan samping"}],
             "motif_layout": {"panels": {"front": {"region": "m1", "label": "manusia"}},
                              "avoid": [{"region": "z1", "label": "kepala kain"}]}}
    text = tryon_ai.build_messages(Image.new("RGB", (80, 120)), Image.new("RGBA", (60, 80)),
                                   Image.new("RGB", (64, 64)), "Tunik", state)[0]["content"][0]["text"]
    assert "- puff sleeves\n" in text and "- belahan samping\n" in text  # English when the LLM gave it
    assert "'manusia' motif placed only on the front body" in text and "'kepala kain' not used" in text
    assert "Add no other details" in text and "do not invent new motifs" in text and "not instructions" in text


def test_the_avatar_request_sends_the_mannequin_not_a_photo():
    parts = tryon_ai.build_avatar_messages(Image.new("RGB", (768, 1024)), Image.new("RGBA", (60, 80)),
                                           Image.new("RGB", (64, 64)), "Tunik",
                                           {"style": [{"part": "silhouette", "text": "oversize"}]})[0]["content"]
    text = parts[0]["text"]
    assert len([p for p in parts if p["type"] == "image_url"]) == 3
    assert "mannequin" in text and "same body proportions" in text and "- oversize\n" in text


def test_the_front_picture_is_the_body_alone_on_a_plain_background():
    import numpy as np

    verts = np.array([[-0.2, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 1.7, 0.0]])
    image = avatar.draw_front(verts, np.array([[0, 1, 2]]), size=(100, 200))
    assert image.size == (100, 200)
    assert image.getpixel((2, 2)) == avatar.FRONT_BG  # background
    assert image.getpixel((50, 150)) != avatar.FRONT_BG  # the body


# ---------- the AI avatar preview through the API and the worker ----------

@pytest.fixture
def image_ai(monkeypatch):
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "g/img")
    monkeypatch.setattr(tryon_ai.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(tryon_ai.settings, "openrouter_api_key", "k")
    monkeypatch.setattr(handlers, "_body_model", lambda gender: f"smplx-{gender}")
    pictured = []

    def front_picture(body, height_cm, values):
        pictured.append({"body": body, "height": height_cm, "values": values})
        return Image.new("RGB", (768, 1024), avatar.FRONT_BG), values

    monkeypatch.setattr(avatar, "front_picture", front_picture)
    calls = []

    def fake(messages, *, model, timeout=150):
        calls.append({"messages": messages, "model": model})
        buf = io.BytesIO()
        Image.new("RGB", (30, 40), (120, 20, 40)).save(buf, format="PNG")
        return ImageResult(png=buf.getvalue(), usage={"cost": 0.04})

    monkeypatch.setattr(tryon_ai.llm_client, "edit_image", fake)
    return {"calls": calls, "pictured": pictured}


def _ai_avatar(client, h, cust, mset, **extra):
    return client.post(f"{API}/customizations/{cust['id']}/avatar-previews", headers=h,
                       json={"measurement_set_id": mset["id"], "use_ai": True, **extra})


def test_ai_avatar_dresses_the_measured_body_with_the_style(client, session, ai, h, make_listing, image_ai):
    cust = _create(client, h, make_listing(), code="T05")
    _add_texture(session, make_listing, cust)
    _apply(client, h, cust["id"], 1, changes={"style": [{"part": "silhouette", "text": "oversize"}]})
    mset = _mset(client, h)
    r = _ai_avatar(client, h, cust, mset, gender="female")
    assert r.status_code == 202, r.text
    queued = r.json()["data"]
    assert queued["kind"] == "avatar_ai" and "avatar dari ukuranmu" in queued["label"]
    run_jobs(session)
    done = client.get(f"{API}/previews/{queued['id']}", headers=h).json()["data"]
    assert done["status"] == "completed_with_warnings" and done["method"] == "ai_avatar_edit:g/img"
    assert any(w.startswith("ai_cost_usd") for w in done["warnings"])
    assert not any("Gaya bebas tidak digambar" in w for w in done["warnings"])  # the AI did draw it
    got = client.get(done["url"])
    assert got.status_code == 200 and Image.open(io.BytesIO(got.content)).size == (30, 40)
    assert image_ai["pictured"][0]["body"] == "smplx-female" and image_ai["pictured"][0]["height"] == 170
    assert image_ai["pictured"][0]["values"]["chest_circumference"] == DIMS["chest_circumference"]
    text = image_ai["calls"][0]["messages"][0]["content"][0]["text"]
    assert "mannequin" in text and "- oversize\n" in text
    event = session.scalar(select(AuditEvent).where(AuditEvent.action == "avatar.sent_to_ai_image_service"))
    assert event is not None and event.meta["model"] == "g/img"
    # a new design revision makes it stale, like every other preview
    _apply(client, h, cust["id"], 2, changes={"style": []})
    assert client.get(f"{API}/previews/{queued['id']}", headers=h).json()["data"]["status"] == "stale"


def test_ai_avatar_is_refused_without_an_image_model(client, h, make_listing, monkeypatch):
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "")
    cust = _create(client, h, make_listing())
    r = _ai_avatar(client, h, cust, _mset(client, h))
    assert r.status_code == 503 and "belum dikonfigurasi" in r.json()["error"]["message"]


def test_a_provider_failure_fails_the_ai_avatar_honestly(client, session, ai, h, make_listing, image_ai, monkeypatch):
    def boom(messages, *, model, timeout=150):
        raise RuntimeError("HTTP 402")

    monkeypatch.setattr(tryon_ai.llm_client, "edit_image", boom)
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    queued = _ai_avatar(client, h, cust, _mset(client, h)).json()["data"]
    run_jobs(session)
    done = client.get(f"{API}/previews/{queued['id']}", headers=h).json()["data"]
    assert done["status"] == "failed" and done["url"] is None
    assert any("Avatar AI gagal" in w and "HTTP 402" in w for w in done["warnings"])


def test_the_consent_notice_says_what_the_ai_avatar_sends(client):
    notice = client.get(f"{API}/photo-consent-notice").json()["data"]["ai_tryon"]["avatar_notice"]
    assert "tanpa foto" in notice and "pihak ketiga" in notice
