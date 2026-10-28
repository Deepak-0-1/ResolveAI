"""Analytics and dashboard metrics router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from resolveai_api.deps import get_current_user
from resolveai_api.schemas import (
    EscalationActivity,
    KnowledgeBaseStats,
    OverviewAnalyticsOut,
    PriorityDistribution,
    StatusDistribution,
)
from resolveai_db.models import (
    AuditLog,
    DocumentStatus,
    Feedback,
    KnowledgeDocument,
    Ticket,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)
from resolveai_db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewAnalyticsOut)
def get_overview_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OverviewAnalyticsOut:
    """Aggregate real database statistics for the Overview Dashboard.
    Results are scoped to the current user if not an admin.
    """
    is_admin = user.role == UserRole.admin

    # Base query for tickets
    ticket_q = db.query(Ticket)
    if not is_admin:
        ticket_q = ticket_q.filter(Ticket.user_id == user.id)

    all_tickets = ticket_q.all()
    total_tickets = len(all_tickets)

    # Status distribution
    status_counts: dict[str, int] = {s.value: 0 for s in TicketStatus}
    priority_counts: dict[str, int] = {p.value: 0 for p in TicketPriority}
    category_counts: dict[str, int] = {}

    for t in all_tickets:
        status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1
        priority_counts[t.priority.value] = priority_counts.get(t.priority.value, 0) + 1
        cat = t.category or "Uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    status_dist = StatusDistribution(
        open=status_counts.get("open", 0),
        pending=status_counts.get("pending", 0),
        escalated=status_counts.get("escalated", 0),
        resolved=status_counts.get("resolved", 0),
        closed=status_counts.get("closed", 0),
    )

    priority_dist = PriorityDistribution(
        low=priority_counts.get("low", 0),
        medium=priority_counts.get("medium", 0),
        high=priority_counts.get("high", 0),
        critical=priority_counts.get("critical", 0),
    )

    # Knowledge Base statistics (admin sees all, customer sees global indexed count)
    kb_docs = db.query(KnowledgeDocument).all()
    total_kb = len(kb_docs)
    indexed_kb = sum(1 for d in kb_docs if d.status == DocumentStatus.indexed)
    failed_kb = sum(1 for d in kb_docs if d.status == DocumentStatus.failed)
    total_chunks = sum(d.chunk_count for d in kb_docs if d.status == DocumentStatus.indexed)

    kb_stats = KnowledgeBaseStats(
        total_documents=total_kb,
        indexed_documents=indexed_kb,
        failed_documents=failed_kb,
        total_chunks=total_chunks,
    )

    # Recent escalation activity
    # Fetch recent escalated tickets
    escalated_tickets_q = (
        db.query(Ticket)
        .filter(Ticket.status == TicketStatus.escalated)
        .order_by(Ticket.updated_at.desc())
    )
    if not is_admin:
        escalated_tickets_q = escalated_tickets_q.filter(Ticket.user_id == user.id)

    recent_escalated_tickets = escalated_tickets_q.limit(10).all()

    # Match with audit log for escalation reasons if recorded
    recent_escalations: list[EscalationActivity] = []
    for et in recent_escalated_tickets:
        # Check audit log for specific escalation reason
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.resource_id == et.id)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        reason = "Awaiting human agent review"
        if audit and audit.detail:
            reason = audit.detail.get("escalation_reason") or audit.detail.get("reason") or reason

        recent_escalations.append(
            EscalationActivity(
                ticket_id=et.id,
                subject=et.subject,
                reason=reason,
                timestamp=et.updated_at or et.created_at,
                priority=et.priority.value,
            )
        )

    # AI resolution stats from AuditLog (chat.agent action)
    audit_chat_q = db.query(AuditLog).filter(AuditLog.action == "chat.agent")
    if not is_admin:
        audit_chat_q = audit_chat_q.filter(AuditLog.user_id == user.id)

    chat_audits = audit_chat_q.all()
    ai_escalations = sum(
        1 for a in chat_audits if a.detail and a.detail.get("status") == "escalated"
    )
    ai_resolutions = sum(
        1 for a in chat_audits if a.detail and a.detail.get("status") == "answered"
    )

    # Feedback counts
    feedback_q = db.query(Feedback)
    if not is_admin:
        feedback_q = feedback_q.filter(Feedback.user_id == user.id)

    feedbacks = feedback_q.all()
    positive_fb = sum(1 for f in feedbacks if f.rating == 1)
    negative_fb = sum(1 for f in feedbacks if f.rating == -1)

    return OverviewAnalyticsOut(
        total_tickets=total_tickets,
        open_tickets=status_dist.open,
        resolved_tickets=status_dist.resolved + status_dist.closed,
        escalated_tickets=status_dist.escalated,
        status_distribution=status_dist,
        priority_distribution=priority_dist,
        category_distribution=category_counts,
        kb_stats=kb_stats,
        recent_escalations=recent_escalations,
        ai_resolutions_count=ai_resolutions,
        ai_escalations_count=ai_escalations,
        feedback_positive=positive_fb,
        feedback_negative=negative_fb,
    )
