"""Shared RAG data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedDocument:
    title: str
    text: str
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)
