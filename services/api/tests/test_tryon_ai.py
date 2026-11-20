"""Fit On drawn by an image model: the request it sends, what it does with the reply, and the fallbacks."""
import base64
import io
import json

import pytest
from PIL import Image
from sqlalchemy import select

from app.ml import llm_client
from app.ml.vision import tryon_ai


def _png(color=(10, 20, 30), size=(8, 6)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_edit_image_sends_the_images_and_decodes_the_reply(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout):
        sent["body"], sent["auth"], sent["url"] = json.loads(req.data), req.headers["Authorization"], req.full_url
        url = "data:image/png;base64," + base64.b64encode(_png((1, 2, 3))).decode()
        return _Resp(json.dumps({"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}],
                                 "usage": {"cost": 0.05}}).encode())

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_client.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(llm_client.settings, "openrouter_api_key", "k")
    out = llm_client.edit_image([{"role": "user", "content": "x"}], model="m/img")
    assert Image.open(io.BytesIO(out.png)).getpixel((0, 0)) == (1, 2, 3) and out.usage["cost"] == 0.05
    assert sent["body"]["model"] == "m/img" and sent["body"]["modalities"] == ["image", "text"]
    assert sent["url"].endswith("/chat/completions") and sent["auth"] == "Bearer k"


def test_an_image_only_model_is_asked_again_for_the_image_alone(monkeypatch):
    sent = []

    def fake_urlopen(req, timeout):
        body = json.loads(req.data)
        sent.append(body["modalities"])
        if body["modalities"] == ["image", "text"]:
            raise llm_client.urllib.error.HTTPError(
                req.full_url, 404, "nf", {}, io.BytesIO(b'{"error":{"message":"No endpoints found that support '
                                                         b'the requested output modalities: image, text"}}'))
        url = "data:image/png;base64," + base64.b64encode(_png((4, 5, 6))).decode()
        return _Resp(json.dumps({"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}).encode())

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_client.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(llm_client.settings, "openrouter_api_key", "k")
    out = llm_client.edit_image([{"role": "user", "content": "x"}], model="seed/img")
    assert sent == [["image", "text"], ["image"]]
    assert Image.open(io.BytesIO(out.png)).getpixel((0, 0)) == (4, 5, 6)


def test_other_refusals_are_not_retried(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        raise llm_client.urllib.error.HTTPError(req.full_url, 403, "f", {},
                                                io.BytesIO(b"This model is not available in your region."))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_client.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(llm_client.settings, "openrouter_api_key", "k")
    with pytest.raises(RuntimeError, match="HTTP 403"):
        llm_client.edit_image([], model="m")
    assert len(calls) == 1


def test_a_reply_without_an_image_is_a_provider_failure_not_an_answer(monkeypatch):
    monkeypatch.setattr(llm_client.urllib.request, "urlopen",
                        lambda req, timeout: _Resp(json.dumps({"choices": [{"message": {"content": "no"}}]}).encode()))
    monkeypatch.setattr(llm_client.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(llm_client.settings, "openrouter_api_key", "k")
    with pytest.raises(RuntimeError, match="tidak mengembalikan gambar"):
        llm_client.edit_image([], model="m")


def test_image_editing_is_only_offered_through_openrouter(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "ollama")
    with pytest.raises(RuntimeError, match="OpenRouter"):
        llm_client.edit_image([], model="m")


def test_the_request_has_the_person_the_drawing_and_the_fabric_and_says_what_to_keep():
    messages = tryon_ai.build_messages(Image.new("RGB", (3000, 2000), "white"), Image.new("RGBA", (60, 80)),
                                       Image.new("RGB", (512, 512)), "Outer", {"collar": "shawl", "pockets": "none"})
    parts = messages[0]["content"]
    images = [p for p in parts if p["type"] == "image_url"]
    assert len(images) == 3 and all(i["image_url"]["url"].startswith("data:image/jpeg;base64,") for i in images)
    person = Image.open(io.BytesIO(base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1])))
    assert max(person.size) == tryon_ai.SEND_MAX_PX  # shrunk before it leaves, less data and cheaper
    text = next(p["text"] for p in parts if p["type"] == "text")
    assert "Outer" in text and "shawl" in text and "face" in text and "same person" in text
    # an option that is off is not an instruction: the design sentence names the collar and nothing else
    design = text.split("wears this garment: ")[1].split(".\n")[0]
    assert design == "Outer: a shawl collar"


# ---------- through the API and the worker ----------

from test_ai import (  # noqa: F401
    FakeDetector,
    _add_texture,
    _jpeg,
    _photo,
    _pose,
    ai,
    run_jobs,
    use_pose,
)
from test_customization import _create, buyer, entry, h, make_listing, synced  # noqa: F401

from app.ml.llm_client import ImageResult
from app.models import AuditEvent, Preview

API = "/api/v1"


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "g/img")
    monkeypatch.setattr(tryon_ai.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(tryon_ai.settings, "openrouter_api_key", "k")
    calls = []

    def fake(messages, *, model, timeout=150):
        calls.append({"messages": messages, "model": model})
        return ImageResult(png=_png((200, 30, 30), (40, 60)), usage={"cost": 0.067})

    monkeypatch.setattr(tryon_ai.llm_client, "edit_image", fake)
    return calls


def _try_on(client, session, h, make_listing, monkeypatch, **body):
    use_pose(monkeypatch, _pose())
    cust = _create(client, h, make_listing())
    _add_texture(session, make_listing, cust)
    photo, _ = _photo(client, h)
    r = client.post(f"{API}/customizations/{cust['id']}/photo-try-ons", headers=h,
                    json={"body_photo_id": photo["id"], **body})
    return r, photo


def test_the_consent_notice_says_whether_ai_fit_on_exists_and_what_it_sends(client, monkeypatch):
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "")
    off = client.get(f"{API}/photo-consent-notice").json()["data"]["ai_tryon"]
    assert off["available"] is False
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "g/img")
    monkeypatch.setattr(tryon_ai.settings, "llm_provider", "openrouter")
    monkeypatch.setattr(tryon_ai.settings, "openrouter_api_key", "k")
    on = client.get(f"{API}/photo-consent-notice").json()["data"]["ai_tryon"]
    assert on["available"] is True and "pihak ketiga" in on["notice"] and "Wajah" in on["notice"]


def test_ai_fit_on_is_refused_when_no_image_model_is_configured(client, session, ai, h, monkeypatch, make_listing):
    monkeypatch.setattr(tryon_ai.settings, "llm_image_model", "")
    r, _ = _try_on(client, session, h, make_listing, monkeypatch, use_ai=True)
    assert r.status_code == 503 and "belum dikonfigurasi" in r.json()["error"]["message"]


def test_without_opt_in_the_photo_never_leaves_the_server(client, session, ai, ai_on, h, monkeypatch, make_listing):
    r, _ = _try_on(client, session, h, make_listing, monkeypatch)  # use_ai left off
    run_jobs(session)
    out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
    assert out["method"] == "pose_landmark_composite_v1" and ai_on == []


def test_ai_fit_on_sends_the_photo_with_consent_records_it_and_labels_the_result(
        client, session, ai, ai_on, h, monkeypatch, make_listing):
    r, photo = _try_on(client, session, h, make_listing, monkeypatch, use_ai=True)
    assert r.status_code == 202
    run_jobs(session)
    out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
    assert out["status"] == "completed_with_warnings" and out["method"] == "ai_image_edit:g/img"
    assert "model gambar AI" in out["warnings"][0] and any(w.startswith("ai_cost_usd") for w in out["warnings"])
    assert len(ai_on) == 1 and ai_on[0]["model"] == "g/img"
    image = Image.open(io.BytesIO(client.get(out["url"]).content))
    assert image.size == (40, 60)  # what the model returned, not the local overlay
    event = session.scalar(select(AuditEvent).where(AuditEvent.action == "photo.sent_to_ai_image_service"))
    assert event is not None and event.target_id == photo["id"] and event.meta["model"] == "g/img"
    assert client.get(f"{API}/files/{session.get(Preview, out['id']).file_id}").status_code == 403  # still private


def test_when_the_provider_fails_the_fallback_is_shown_as_a_fallback(client, session, ai, ai_on, h, monkeypatch,
                                                                     make_listing):
    def boom(messages, *, model, timeout=150):
        raise RuntimeError("HTTP 402")

    monkeypatch.setattr(tryon_ai.llm_client, "edit_image", boom)
    r, _ = _try_on(client, session, h, make_listing, monkeypatch, use_ai=True)
    run_jobs(session)
    out = client.get(f"{API}/previews/{r.json()['data']['id']}", headers=h).json()["data"]
    assert out["method"] == "pose_landmark_composite_v1"  # the local overlay, not labelled as AI
    assert any(w.startswith("ai_failed") and "HTTP 402" in w for w in out["warnings"])
