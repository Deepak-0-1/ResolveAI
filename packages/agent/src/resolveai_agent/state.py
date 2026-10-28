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

    # Investigation workflow fields
    is_investigation: bool
    jira_issue_key: str | None
    issue_summary: str | None
    issue_description: str | None
    issue_comments: list[dict[str, Any]]
    similar_tickets: list[dict[str, Any]]
    evidence_sufficient: bool
    confidence_score: float
    confidence_method: str
    missing_information_or_risks: list[str]
    investigation_steps: list[str]
    human_approval_required: bool
    investigation_report: dict[str, Any]
    draft_jira_comment: str | None

    trace: list[str]

