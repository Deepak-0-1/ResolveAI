"""LangGraph agent state."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    user_id: str
    user_role: str
    ticket_id: str | None

    category: str
    priority: str
    urgency: str

    route: str  # answer | tools | escalate
    tool_name: str | None
    tool_result: dict[str, Any] | None
    tools_used: list[str]

    status: str
    answer: str
    citations: list[dict[str, Any]]
    escalation_reason: str | None
    retrieval_hit_count: int
    top_score: float | None

    trace: list[str]
