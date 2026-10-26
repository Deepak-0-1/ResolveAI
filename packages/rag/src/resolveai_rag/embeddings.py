"""Embedding client — Ollama by default; swappable for tests."""

from __future__ import annotations

from typing import Protocol

import httpx

from resolveai_common.retry import with_retries
from resolveai_common.settings import Settings, get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...


class OllamaEmbedder:
    """Calls Ollama `/api/embeddings` for each text (compatible with nomic-embed-text)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def dimensions(self) -> int:
        return self.settings.embedding_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        timeout = self.settings.embed_timeout_seconds
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/embeddings"
        retries = self.settings.http_max_retries
        backoff = self.settings.http_retry_backoff_seconds

        def _one(text: str) -> list[float]:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    json={"model": self.settings.ollama_embed_model, "prompt": text},
                )
                response.raise_for_status()
                payload = response.json()
            vector = payload.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Ollama returned an empty embedding")
            return vector

        for text in texts:
            vectors.append(
                with_retries(
                    lambda t=text: _one(t),
                    retries=retries,
                    backoff_seconds=backoff,
                    retry_on=(httpx.HTTPError, RuntimeError),
                    operation="ollama_embed",
                )
            )
        return vectors


class HashEmbedder:
    """Deterministic fake embedder for unit tests (no Ollama required)."""

    def __init__(self, dimensions: int = 32) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dimensions
            for i, ch in enumerate(text.encode("utf-8")):
                vec[i % self._dimensions] += (ch % 31) / 31.0
            # L2 normalize
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            result.append([v / norm for v in vec])
        return result
