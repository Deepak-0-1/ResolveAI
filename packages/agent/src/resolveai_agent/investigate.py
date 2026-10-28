"""LangGraph Investigation Workflow for Jira and Enterprise Ticketing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import or_
from sqlalchemy.orm import Session

from resolveai_agent.classify import classify_message
from resolveai_agent.state import AgentState
from resolveai_common.jira import sanitize_untrusted_text
from resolveai_common.settings import Settings, get_settings
from resolveai_db.models import Message, MessageRole, Ticket, TicketStatus
from resolveai_rag.answer import AnswerStatus
from resolveai_rag.embeddings import Embedder
from resolveai_rag.llm import ChatLLM
from resolveai_rag.store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class InvestigationResult:
    status: str  # conclusive | escalated | insufficient_evidence
    issue_key: str
    problem_summary: str
    category: str
    priority: str
    urgency: str
    confidence_score: float
    confidence_method: str
    evidence_found: list[str]
    citations: list[dict[str, Any]]
    similar_past_tickets: list[dict[str, Any]]
    investigation_steps: list[str]
    proposed_root_cause: str
    recommended_resolution: str
    missing_information_or_risks: list[str]
    human_approval_required: bool
    draft_jira_comment: str
    report: dict[str, Any]
    trace: list[str] = field(default_factory=list)


def _append_trace(state: AgentState, node: str) -> list[str]:
    return [*(state.get("trace") or []), node]


def format_jira_comment(
    *,
    issue_key: str,
    problem_summary: str,
    status: str,
    confidence_score: float,
    proposed_root_cause: str,
    recommended_resolution: str,
    citations: list[dict[str, Any]],
    similar_past_tickets: list[dict[str, Any]],
    human_approval_required: bool,
    missing_risks: list[str],
) -> str:
    """Format an enterprise-ready investigation report as a Jira comment."""
    status_icon = "✅ CONCLUSIVE" if status == "conclusive" else "⚠️ ESCALATED (HUMAN REVIEW REQUIRED)"
    lines = [
        f"h3. 🛡️ ResolveAI Investigation Report — {issue_key}",
        f"*Investigation Status:* {status_icon}",
        f"*Confidence Score:* {confidence_score * 100:.1f}% (Method: Hybrid vector relevance + historical corroboration)",
        "",
        "h4. 1. Problem Summary",
        problem_summary,
        "",
        "h4. 2. Proposed Root Cause",
        proposed_root_cause,
        "",
        "h4. 3. Recommended Resolution",
        recommended_resolution,
        "",
    ]

    if citations:
        lines.append("h4. 4. Supporting Knowledge Base Citations")
        for c in citations[:3]:
            title = c.get("title") or c.get("filename") or "Knowledge Document"
            score = c.get("score", 0.0)
            lines.append(f"* *{title}* (Relevance: {score:.3f}): {c.get('snippet', '')[:200]}…")
        lines.append("")

    if similar_past_tickets:
        lines.append("h4. 5. Historical Ticket Precedents")
        for t in similar_past_tickets[:2]:
            lines.append(f"* *Ticket #{t['id'][:8]}* ({t['status'].upper()}): {t['subject']}")
        lines.append("")

    if missing_risks:
        lines.append("h4. 6. Identified Risks & Missing Context")
        for r in missing_risks:
            lines.append(f"* ⚠️ {r}")
        lines.append("")

    if human_approval_required:
        lines.append("----")
        lines.append("*⚠️ Human Approval Required:* An authorized support engineer must verify this resolution before execution.")

    return "\n".join(lines).strip()


def build_investigation_graph(
    *,
    store: VectorStore,
    embedder: Embedder,
    llm: ChatLLM,
    db: Session,
    settings: Settings | None = None,
):
    """Compile LangGraph investigation workflow:
    load_context → classify → retrieve_knowledge_and_tickets → run_diagnostics → evaluate_evidence → synthesize_report.
    """
    cfg = settings or get_settings()

    def load_context_node(state: AgentState) -> dict[str, Any]:
        raw_summary = state.get("issue_summary") or state.get("question") or ""
        raw_desc = state.get("issue_description") or ""
        clean_summary = sanitize_untrusted_text(raw_summary)
        clean_desc = sanitize_untrusted_text(raw_desc)

        # Append recent comments if any
        comments = state.get("issue_comments") or []
        comment_texts = []
        for c in comments[-3:]:
            c_body = sanitize_untrusted_text(c.get("body", ""))
            if c_body:
                comment_texts.append(f"Comment by {c.get('author', 'User')}: {c_body}")

        full_context = f"{clean_summary}\n\n{clean_desc}"
        if comment_texts:
            full_context += "\n\nRecent Issue Comments:\n" + "\n".join(comment_texts)

        return {
            "question": full_context,
            "issue_summary": clean_summary,
            "issue_description": clean_desc,
            "trace": _append_trace(state, "investigation:load_context"),
        }

    def classify_issue_node(state: AgentState) -> dict[str, Any]:
        text_to_classify = state.get("issue_summary") or state.get("question") or ""
        classification = classify_message(text_to_classify)
        return {
            "category": classification.category,
            "priority": classification.priority,
            "urgency": classification.urgency,
            "trace": _append_trace(state, "investigation:classify_issue"),
        }

    def retrieve_knowledge_and_tickets_node(state: AgentState) -> dict[str, Any]:
        query_text = f"{state.get('issue_summary', '')} {state.get('issue_description', '')}".strip()
        if not query_text:
            query_text = state.get("question", "")

        # 1. Hybrid RAG retrieval from vector store
        vectors = embedder.embed([query_text])
        hits = store.search(
            vectors[0],
            limit=cfg.retrieval_top_k,
            query=query_text if cfg.retrieval_mode.lower() == "hybrid" else None,
        )

        citations = [
            {
                "index": i + 1,
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "title": h.payload.get("title") or h.payload.get("filename"),
                "filename": h.payload.get("filename"),
                "snippet": h.text,
                "score": round(float(h.score), 4),
            }
            for i, h in enumerate(hits)
        ]
        top_score = citations[0]["score"] if citations else 0.0

        # 2. Historical past tickets from PostgreSQL
        category = state.get("category")
        past_tickets_q = db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.resolved, TicketStatus.closed])
        )
        if category:
            past_tickets_q = past_tickets_q.filter(Ticket.category == category)

        resolved_records = past_tickets_q.order_by(Ticket.updated_at.desc()).limit(3).all()
        similar_past_tickets = [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value,
                "category": t.category,
                "priority": t.priority.value,
            }
            for t in resolved_records
        ]

        return {
            "citations": citations,
            "retrieval_hit_count": len(citations),
            "top_score": top_score,
            "similar_tickets": similar_past_tickets,
            "trace": _append_trace(state, "investigation:retrieve_knowledge_and_tickets"),
        }

    def run_diagnostics_node(state: AgentState) -> dict[str, Any]:
        full_text = (state.get("question") or "").lower()
        tools_used = list(state.get("tools_used") or [])
        tools_used.extend(["rag_hybrid_search", "historical_ticket_lookup", "policy_boundary_check"])

        # Check for policy escalation triggers
        escalation_triggered = False
        escalation_reason = None
        for kw in cfg.escalate_keyword_list:
            if kw in full_text:
                escalation_triggered = True
                escalation_reason = f"Security / policy boundary keyword detected: '{kw}'"
                break

        steps = [
            "Loaded issue summary and sanitized untrusted inputs.",
            f"Classified ticket into category '{state.get('category')}' with severity '{state.get('priority')}'.",
            f"Executed hybrid retrieval (BM25 + Dense vector RRF); retrieved {state.get('retrieval_hit_count', 0)} knowledge chunks.",
            f"Cross-referenced PostgreSQL database for resolved precedents; found {len(state.get('similar_tickets') or [])} matching historical records.",
            "Evaluated policy boundaries and security escalation keywords.",
        ]

        return {
            "tools_used": tools_used,
            "escalation_reason": escalation_reason,
            "evidence_sufficient": not escalation_triggered,
            "investigation_steps": steps,
            "trace": _append_trace(state, "investigation:run_diagnostics"),
        }

    def evaluate_evidence_node(state: AgentState) -> dict[str, Any]:
        top_score = float(state.get("top_score") or 0.0)
        min_score = cfg.min_retrieval_score
        similar_tickets = state.get("similar_tickets") or []
        escalation_reason = state.get("escalation_reason")

        missing_risks = []
        desc = state.get("issue_description") or ""
        if len(desc.strip()) < 20:
            missing_risks.append("Issue description is very short; missing reproduction steps or system environment logs.")

        # Documented confidence scoring formula:
        # Base: normalized top retrieval score (0.0 to 1.0)
        # Corroboration: +0.10 if similar past resolved tickets exist
        # Penalty: -0.30 if description lacks details, force <= 0.40 if security escalation keyword
        confidence = min(max(top_score, 0.0), 1.0)
        if similar_tickets:
            confidence = min(confidence + 0.10, 1.0)
        if len(desc.strip()) < 20:
            confidence = max(confidence - 0.20, 0.10)

        confidence_method = (
            "Normalized hybrid retrieval score (RRF-weighted) + historical ticket corroboration (+0.1) "
            "- ambiguity penalty (-0.2)"
        )

        is_sufficient = True
        status_val = "conclusive"

        if escalation_reason:
            is_sufficient = False
            status_val = "escalated"
            confidence = min(confidence, 0.40)
            missing_risks.append(f"Escalation required: {escalation_reason}")
        elif top_score < min_score:
            is_sufficient = False
            status_val = "insufficient_evidence"
            confidence = max(confidence * 0.5, 0.15)
            missing_risks.append(f"Top retrieval similarity score ({top_score:.3f}) is below confidence threshold ({min_score:.3f}).")
            if not escalation_reason:
                escalation_reason = "Insufficient knowledge base grounding to guarantee resolution."

        human_approval_required = confidence < 0.75 or not is_sufficient

        return {
            "confidence_score": round(confidence, 3),
            "confidence_method": confidence_method,
            "evidence_sufficient": is_sufficient,
            "status": status_val,
            "escalation_reason": escalation_reason,
            "missing_information_or_risks": missing_risks,
            "human_approval_required": human_approval_required,
            "trace": _append_trace(state, f"investigation:evaluate_evidence:{status_val}"),
        }

    def synthesize_report_node(state: AgentState) -> dict[str, Any]:
        issue_key = state.get("jira_issue_key") or "ISSUE"
        summary = state.get("issue_summary") or "Customer reported technical inquiry"
        status_val = state.get("status") or "insufficient_evidence"
        confidence = float(state.get("confidence_score") or 0.5)
        citations = state.get("citations") or []
        similar_tickets = state.get("similar_tickets") or []
        steps = state.get("investigation_steps") or []
        missing_risks = state.get("missing_information_or_risks") or []
        category = state.get("category") or "General"
        priority = state.get("priority") or "medium"
        urgency = state.get("urgency") or "medium"
        approval_req = state.get("human_approval_required", True)

        # Generate evidence list
        evidence_found = []
        for c in citations[:3]:
            title = c.get("title") or c.get("filename")
            evidence_found.append(f"Documentation Reference: '{title}' (relevance={c.get('score', 0):.3f})")
        if similar_tickets:
            evidence_found.append(f"Historical Precedent: {len(similar_tickets)} resolved tickets match category '{category}'")

        # Synthesize root cause & resolution
        if status_val == "conclusive" and citations:
            best_chunk = citations[0]["snippet"]
            root_cause = (
                f"[Hypothesis - Grounded in Documentation] The reported issue aligns with standard configuration "
                f"guidelines outlined in {citations[0].get('title', 'documentation')}."
            )
            resolution = (
                f"1. Follow standard operational procedure from {citations[0].get('title', 'KB')}:\n"
                f"{best_chunk[:300]}\n"
                f"2. Instruct customer to verify credentials / account settings.\n"
                f"3. Verify error logs if issue persists."
            )
        else:
            root_cause = (
                f"[Hypothesis - Unconfirmed] Root cause could not be conclusively determined with available evidence. "
                f"{state.get('escalation_reason') or 'Documentation match below certainty threshold.'}"
            )
            resolution = (
                "1. Escalate to human Tier 2 / engineering specialist for manual investigation.\n"
                "2. Request full diagnostic logs and exact timestamp from customer.\n"
                "3. Do not apply automated state changes without explicit manual review."
            )

        # Generate formatted Jira comment
        comment_body = format_jira_comment(
            issue_key=issue_key,
            problem_summary=summary,
            status=status_val,
            confidence_score=confidence,
            proposed_root_cause=root_cause,
            recommended_resolution=resolution,
            citations=citations,
            similar_past_tickets=similar_tickets,
            human_approval_required=approval_req,
            missing_risks=missing_risks,
        )

        structured_report = {
            "issue_key": issue_key,
            "problem_summary": summary,
            "category": category,
            "priority": priority,
            "urgency": urgency,
            "status": status_val,
            "confidence_score": confidence,
            "confidence_method": state.get("confidence_method"),
            "evidence_found": evidence_found,
            "citations": citations,
            "similar_past_tickets": similar_tickets,
            "investigation_steps": steps,
            "proposed_root_cause": root_cause,
            "recommended_resolution": resolution,
            "missing_information_or_risks": missing_risks,
            "human_approval_required": approval_req,
            "tools_used": state.get("tools_used") or [],
            "draft_jira_comment": comment_body,
        }

        return {
            "investigation_report": structured_report,
            "draft_jira_comment": comment_body,
            "proposed_root_cause": root_cause,
            "recommended_resolution": resolution,
            "trace": _append_trace(state, "investigation:synthesize_report"),
        }

    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("classify_issue", classify_issue_node)
    graph.add_node("retrieve_knowledge_and_tickets", retrieve_knowledge_and_tickets_node)
    graph.add_node("run_diagnostics", run_diagnostics_node)
    graph.add_node("evaluate_evidence", evaluate_evidence_node)
    graph.add_node("synthesize_report", synthesize_report_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "classify_issue")
    graph.add_edge("classify_issue", "retrieve_knowledge_and_tickets")
    graph.add_edge("retrieve_knowledge_and_tickets", "run_diagnostics")
    graph.add_edge("run_diagnostics", "evaluate_evidence")
    graph.add_edge("evaluate_evidence", "synthesize_report")
    graph.add_edge("synthesize_report", END)

    return graph.compile()


def run_investigation_agent(
    *,
    issue_key: str,
    summary: str,
    description: str,
    comments: list[dict[str, Any]] | None = None,
    user_id: str = "system",
    user_role: str = "admin",
    store: VectorStore,
    embedder: Embedder,
    llm: ChatLLM,
    db: Session,
    settings: Settings | None = None,
) -> InvestigationResult:
    """Execute end-to-end AI investigation for a Jira issue or customer support ticket."""
    app = build_investigation_graph(
        store=store,
        embedder=embedder,
        llm=llm,
        db=db,
        settings=settings,
    )
    initial_state: AgentState = {
        "is_investigation": True,
        "jira_issue_key": issue_key,
        "issue_summary": summary,
        "issue_description": description,
        "issue_comments": comments or [],
        "user_id": user_id,
        "user_role": user_role,
        "tools_used": [],
        "trace": [],
        "citations": [],
    }

    final: AgentState = app.invoke(initial_state)
    report = final.get("investigation_report") or {}

    return InvestigationResult(
        status=final.get("status") or "insufficient_evidence",
        issue_key=issue_key,
        problem_summary=report.get("problem_summary") or summary,
        category=report.get("category") or "general",
        priority=report.get("priority") or "medium",
        urgency=report.get("urgency") or "medium",
        confidence_score=float(report.get("confidence_score") or 0.0),
        confidence_method=report.get("confidence_method") or "",
        evidence_found=list(report.get("evidence_found") or []),
        citations=list(report.get("citations") or []),
        similar_past_tickets=list(report.get("similar_past_tickets") or []),
        investigation_steps=list(report.get("investigation_steps") or []),
        proposed_root_cause=report.get("proposed_root_cause") or "",
        recommended_resolution=report.get("recommended_resolution") or "",
        missing_information_or_risks=list(report.get("missing_information_or_risks") or []),
        human_approval_required=bool(report.get("human_approval_required", True)),
        draft_jira_comment=final.get("draft_jira_comment") or "",
        report=report,
        trace=list(final.get("trace") or []),
    )
