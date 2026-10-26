"""Safe, non-destructive agent tools (lookup / status / draft only)."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from resolveai_db.models import Message, MessageRole, Ticket, UserRole

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def extract_ticket_id(text: str, fallback: str | None = None) -> str | None:
    match = _UUID_RE.search(text)
    if match:
        return match.group(0)
    return fallback


def detect_tool_intent(text: str) -> str | None:
    lowered = text.lower()
    if any(p in lowered for p in ("draft response", "draft a reply", "write a draft")):
        return "create_draft_response"
    if any(p in lowered for p in ("ticket status", "status of ticket", "check status")):
        return "get_ticket_status"
    if any(p in lowered for p in ("look up ticket", "lookup ticket", "get ticket", "find ticket")):
        return "get_ticket"
    # Bare ticket UUID with status-ish wording
    if extract_ticket_id(text) and "status" in lowered:
        return "get_ticket_status"
    if extract_ticket_id(text) and any(p in lowered for p in ("look up", "lookup", "details")):
        return "get_ticket"
    return None


def _can_access(ticket: Ticket, *, user_id: str, user_role: str) -> bool:
    if user_role == UserRole.admin.value:
        return True
    return ticket.user_id == user_id


def get_ticket(
    db: Session,
    ticket_id: str,
    *,
    user_id: str,
    user_role: str,
) -> dict[str, Any]:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        return {"ok": False, "error": "ticket_not_found", "ticket_id": ticket_id}
    if not _can_access(ticket, user_id=user_id, user_role=user_role):
        return {"ok": False, "error": "forbidden", "ticket_id": ticket_id}
    return {
        "ok": True,
        "ticket": {
            "id": ticket.id,
            "subject": ticket.subject,
            "status": ticket.status.value,
            "category": ticket.category,
            "priority": ticket.priority.value,
            "urgency": ticket.urgency.value,
            "user_id": ticket.user_id,
        },
    }


def get_ticket_status(
    db: Session,
    ticket_id: str,
    *,
    user_id: str,
    user_role: str,
) -> dict[str, Any]:
    result = get_ticket(db, ticket_id, user_id=user_id, user_role=user_role)
    if not result.get("ok"):
        return result
    ticket = result["ticket"]
    return {
        "ok": True,
        "ticket_id": ticket["id"],
        "status": ticket["status"],
        "priority": ticket["priority"],
        "urgency": ticket["urgency"],
    }


def create_draft_response(
    db: Session,
    ticket_id: str,
    draft_body: str,
    *,
    user_id: str,
    user_role: str,
) -> dict[str, Any]:
    """Persist a draft reply on the ticket. Does not send email or close the ticket."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        return {"ok": False, "error": "ticket_not_found", "ticket_id": ticket_id}
    if not _can_access(ticket, user_id=user_id, user_role=user_role):
        return {"ok": False, "error": "forbidden", "ticket_id": ticket_id}
    if user_role != UserRole.admin.value and ticket.user_id != user_id:
        return {"ok": False, "error": "forbidden", "ticket_id": ticket_id}

    # Customers may request a draft on their ticket; content is stored as assistant draft.
    content = draft_body.strip()
    if not content.startswith("[DRAFT]"):
        content = f"[DRAFT] {content}"
    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.assistant,
            content=content,
        )
    )
    db.flush()
    return {
        "ok": True,
        "ticket_id": ticket.id,
        "draft_preview": content[:240],
        "sent": False,
        "note": "Draft stored only; no external send.",
    }


def is_valid_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False
