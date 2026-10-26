"""LangGraph support workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from resolveai_agent.classify import classify_message
from resolveai_agent.state import AgentState
from resolveai_agent.tools import (
    create_draft_response,
    detect_tool_intent,
    extract_ticket_id,
    get_ticket,
    get_ticket_status,
)
from resolveai_common.settings import Settings, get_settings
from resolveai_rag.answer import AnswerStatus, answer_question
from resolveai_rag.embeddings import Embedder
from resolveai_rag.llm import ChatLLM
from resolveai_rag.store import VectorStore


@dataclass
class AgentResult:
    status: str
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    escalation_reason: str | None = None
    retrieval_hit_count: int = 0
    top_score: float | None = None
    category: str = "general"
    priority: str = "medium"
    urgency: str = "medium"
    tools_used: list[str] = field(default_factory=list)
    tool_result: dict[str, Any] | None = None
    trace: list[str] = field(default_factory=list)
    ticket_id: str | None = None


def _append_trace(state: AgentState, node: str) -> list[str]:
    return [*(state.get("trace") or []), node]


def build_support_graph(
    *,
    store: VectorStore,
    embedder: Embedder,
    llm: ChatLLM,
    db: Session,
    settings: Settings | None = None,
):
    """Compile classify → route → tools|retrieve → answer|escalate."""
    cfg = settings or get_settings()

    def classify_node(state: AgentState) -> dict[str, Any]:
        result = classify_message(state["question"])
        return {
            "category": result.category,
            "priority": result.priority,
            "urgency": result.urgency,
            "tools_used": list(state.get("tools_used") or []),
            "trace": _append_trace(state, "classify"),
        }

    def route_intent_node(state: AgentState) -> dict[str, Any]:
        tool = detect_tool_intent(state["question"])
        if tool:
            return {
                "route": "tools",
                "tool_name": tool,
                "trace": _append_trace(state, "route_intent:tools"),
            }
        return {
            "route": "retrieve",
            "tool_name": None,
            "trace": _append_trace(state, "route_intent:retrieve"),
        }

    def tools_node(state: AgentState) -> dict[str, Any]:
        tool_name = state.get("tool_name") or "get_ticket"
        ticket_id = extract_ticket_id(state["question"], state.get("ticket_id"))
        used = list(state.get("tools_used") or [])
        used.append(tool_name)

        if not ticket_id:
            return {
                "status": AnswerStatus.refused.value,
                "answer": (
                    "I can look up tickets, but I need a ticket UUID. "
                    "Example: look up ticket 11111111-1111-1111-1111-111111111111"
                ),
                "citations": [],
                "tools_used": used,
                "tool_result": {"ok": False, "error": "missing_ticket_id"},
                "trace": _append_trace(state, "tools:missing_id"),
            }

        user_id = state["user_id"]
        user_role = state["user_role"]
        if tool_name == "get_ticket_status":
            result = get_ticket_status(db, ticket_id, user_id=user_id, user_role=user_role)
            answer = (
                f"Ticket {ticket_id} status is **{result.get('status')}** "
                f"(priority={result.get('priority')}, urgency={result.get('urgency')})."
                if result.get("ok")
                else f"Could not get status: {result.get('error')}."
            )
        elif tool_name == "create_draft_response":
            # Draft grounded from KB when possible
            grounded = answer_question(
                question=state["question"],
                store=store,
                embedder=embedder,
                llm=llm,
                settings=cfg,
            )
            draft_text = grounded.answer
            result = create_draft_response(
                db,
                ticket_id,
                draft_text,
                user_id=user_id,
                user_role=user_role,
            )
            if result.get("ok"):
                preview = result.get("draft_preview")
                answer = f"Draft stored on ticket {ticket_id} (not sent). Preview: {preview}"
            else:
                answer = f"Could not create draft: {result.get('error')}."
        else:
            result = get_ticket(db, ticket_id, user_id=user_id, user_role=user_role)
            if result.get("ok"):
                t = result["ticket"]
                answer = (
                    f"Ticket {t['id']}: subject='{t['subject']}', status={t['status']}, "
                    f"category={t['category']}, priority={t['priority']}, urgency={t['urgency']}."
                )
            else:
                answer = f"Could not look up ticket: {result.get('error')}."

        status = AnswerStatus.answered.value if result.get("ok") else AnswerStatus.refused.value
        return {
            "status": status,
            "answer": answer,
            "citations": [],
            "tools_used": used,
            "tool_result": result,
            "ticket_id": ticket_id,
            "trace": _append_trace(state, f"tools:{tool_name}"),
        }

    def retrieve_answer_node(state: AgentState) -> dict[str, Any]:
        grounded = answer_question(
            question=state["question"],
            store=store,
            embedder=embedder,
            llm=llm,
            settings=cfg,
        )
        citations = [
            {
                "index": c.index,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "title": c.title,
                "filename": c.filename,
                "snippet": c.snippet,
                "score": c.score,
            }
            for c in grounded.citations
        ]
        return {
            "status": grounded.status.value,
            "answer": grounded.answer,
            "citations": citations,
            "escalation_reason": grounded.escalation_reason,
            "retrieval_hit_count": grounded.retrieval_hit_count,
            "top_score": grounded.top_score,
            "trace": _append_trace(state, f"retrieve_answer:{grounded.status.value}"),
        }

    def pick_route(
        state: AgentState,
    ) -> Literal["tools", "retrieve_answer"]:
        return "tools" if state.get("route") == "tools" else "retrieve_answer"

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("retrieve_answer", retrieve_answer_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "route_intent")
    graph.add_conditional_edges(
        "route_intent",
        pick_route,
        {
            "tools": "tools",
            "retrieve_answer": "retrieve_answer",
        },
    )
    graph.add_edge("tools", END)
    graph.add_edge("retrieve_answer", END)
    return graph.compile()


def run_support_agent(
    *,
    question: str,
    user_id: str,
    user_role: str,
    store: VectorStore,
    embedder: Embedder,
    llm: ChatLLM,
    db: Session,
    ticket_id: str | None = None,
    settings: Settings | None = None,
) -> AgentResult:
    app = build_support_graph(
        store=store,
        embedder=embedder,
        llm=llm,
        db=db,
        settings=settings,
    )
    final: AgentState = app.invoke(
        {
            "question": question,
            "user_id": user_id,
            "user_role": user_role,
            "ticket_id": ticket_id,
            "tools_used": [],
            "trace": [],
            "citations": [],
        }
    )
    return AgentResult(
        status=final.get("status") or AnswerStatus.refused.value,
        answer=final.get("answer") or "",
        citations=list(final.get("citations") or []),
        escalation_reason=final.get("escalation_reason"),
        retrieval_hit_count=int(final.get("retrieval_hit_count") or 0),
        top_score=final.get("top_score"),
        category=final.get("category") or "general",
        priority=final.get("priority") or "medium",
        urgency=final.get("urgency") or "medium",
        tools_used=list(final.get("tools_used") or []),
        tool_result=final.get("tool_result"),
        trace=list(final.get("trace") or []),
        ticket_id=final.get("ticket_id") or ticket_id,
    )
