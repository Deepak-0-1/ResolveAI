"""Chat LLM client — Ollama by default; FakeLLM for tests."""

from __future__ import annotations

from typing import Protocol

import httpx

from resolveai_common.retry import with_retries
from resolveai_common.settings import Settings, get_settings


class ChatLLM(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


class OllamaChatLLM:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete(self, *, system: str, user: str) -> str:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.settings.ollama_chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.1},
        }

        def _call() -> str:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            message = data.get("message") or {}
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Ollama returned an empty chat response")
            return content.strip()

        return with_retries(
            _call,
            retries=self.settings.http_max_retries,
            backoff_seconds=self.settings.http_retry_backoff_seconds,
            retry_on=(httpx.HTTPError, RuntimeError),
            operation="ollama_chat",
        )


class FakeLLM:
    """Deterministic grounded reply for unit/API tests."""

    def __init__(self, answer: str | None = None) -> None:
        self.answer = answer

    def complete(self, *, system: str, user: str) -> str:
        if self.answer is not None:
            return self.answer
        # Prefer citing source [1] if the prompt includes sources.
        if "[1]" in user or "Source [1]" in user:
            return (
                "Based on the knowledge base, use Forgot password on the login page. "
                "The reset link expires in 30 minutes. [1]"
            )
        return "I do not have enough information in the knowledge base to answer."
