"""Redact secrets from strings before logging."""

from __future__ import annotations

import re

_SENSITIVE = re.compile(
    r"(?i)(authorization|api[_-]?key|jwt|password|secret|token)\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*")


def redact(text: str) -> str:
    cleaned = _BEARER.sub("Bearer [REDACTED]", text)
    return _SENSITIVE.sub(r"\1=[REDACTED]", cleaned)
