"""Minimal OpenAI-compatible chat client shared by the fabric scanner and the story writer.

Works with OpenAI, OpenRouter and Ollama. Every provider problem becomes a RuntimeError, which the
callers turn into a 503: a failed call must never be mistaken for an answer.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import settings

ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}


def endpoint() -> tuple[str, str]:
    """Base URL and API key for the configured provider."""
    key = {"openai": settings.openai_api_key, "openrouter": settings.openrouter_api_key}.get(
        settings.llm_provider, "")
    return ENDPOINTS[settings.llm_provider], key


def configured() -> bool:
    provider = settings.llm_provider
    return provider == "ollama" or (provider == "openai" and bool(settings.openai_api_key)) or (
        provider == "openrouter" and bool(settings.openrouter_api_key))


def provider_name(model: str | None = None) -> str:
    return f"{settings.llm_provider}:{model or settings.llm_model}"


@dataclass
class ChatResult:
    content: str
    annotations: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)  # tokens and, on OpenRouter, the billed cost in USD


def chat(messages: list[dict], *, model: str | None = None, json_mode: bool = True,
         plugins: list[dict] | None = None) -> ChatResult:
    base, key = endpoint()
    body: dict = {"model": model or settings.llm_model, "temperature": 0, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if plugins:
        body["plugins"] = plugins
    if settings.llm_provider == "openrouter":
        body["usage"] = {"include": True}  # OpenRouter reports the billed cost per call
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.vlm_timeout_seconds) as resp:
            data = json.load(resp)
            message = data["choices"][0]["message"]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise RuntimeError(f"Penyedia model menolak permintaan (HTTP {exc.code}): {detail}") from exc
    except (OSError, KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"Penyedia model tidak dapat dihubungi/dibaca: {exc}") from exc
    return ChatResult(content=message.get("content") or "", annotations=message.get("annotations") or [],
                      usage=data.get("usage") or {})


def parse_json(text: str, what: str) -> dict:
    """Parse a model's JSON reply; tolerates a ```json fence. Anything else is a provider failure."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):] if "{" in raw else raw
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"Keluaran {what} tidak berupa JSON yang valid: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Keluaran {what} bukan objek JSON")  # noqa: TRY004 (callers map RuntimeError to 503)
    return data
