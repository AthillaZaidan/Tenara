import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.models.gallery import EMBED_DIM


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Deterministic hashed bag-of-words embedder for tests and offline development."""

    name = "fake-bow-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * EMBED_DIM
            for token in re.findall(r"\w+", text.lower()):
                vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % EMBED_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class FastEmbedEmbedder:
    """Local multilingual model (384-d) via fastembed/ONNX. Model loads lazily on first use."""

    def __init__(self, model_name: str):
        self.name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(self.name)
        return [[float(x) for x in vec] for vec in self._model.embed(texts)]


@lru_cache
def get_embedder() -> Embedder | None:
    if settings.embedder == "fastembed":
        return FastEmbedEmbedder(settings.embedding_model)
    if settings.embedder == "fake":
        return FakeEmbedder()
    return None
