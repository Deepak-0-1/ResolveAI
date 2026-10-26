"""Ticket/message classification — heuristic first (stable), LLM optional later."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Classification:
    category: str
    priority: str
    urgency: str


_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("billing", ["billing", "invoice", "refund", "payment", "seat", "overage", "charge"]),
    ("account", ["password", "login", "mfa", "invite", "subdomain", "profile", "account"]),
    ("api", ["api", "webhook", "rate limit", "x-api-key", "developer"]),
    ("privacy", ["privacy", "pii", "gdpr", "delete workspace", "legal hold", "data deletion"]),
    ("outage", ["outage", "down", "unavailable", "500", "incident"]),
]


def classify_message(text: str) -> Classification:
    lowered = text.lower()
    category = "general"
    for name, keywords in _CATEGORY_RULES:
        if any(k in lowered for k in keywords):
            category = name
            break

    priority = "medium"
    urgency = "medium"
    if any(k in lowered for k in ("critical", "outage", "down", "production broken")):
        priority = "critical"
        urgency = "high"
    elif any(k in lowered for k in ("urgent", "asap", "immediately", "right now")):
        priority = "high"
        urgency = "high"
    elif any(k in lowered for k in ("whenever", "low priority", "no rush")):
        priority = "low"
        urgency = "low"

    # Security-sensitive account actions bump urgency
    if re.search(r"\b(mfa|ssn|delete workspace|chargeback)\b", lowered):
        urgency = "high"
        if priority == "medium":
            priority = "high"

    return Classification(category=category, priority=priority, urgency=urgency)
