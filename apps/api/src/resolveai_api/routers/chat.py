"""Chat via LangGraph support agent."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from resolveai_agent.graph import run_support_agent
from resolveai_api.deps import get_current_user
from resolveai_api.rag_deps import get_embedder, get_llm, get_vector_store
from resolveai_api.schemas import ChatRequest, ChatResponse, CitationOut
from resolveai_common.settings import get_settings
from resolveai_db.models import (
    AuditLog,
    Message,
    MessageRole,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
    User,
    UserRole,
)
from resolveai_db.session import get_db
from resolveai_rag.answer import AnswerStatus
from resolveai_rag.embeddings import Embedder
from resolveai_rag.llm import ChatLLM
from resolveai_rag.store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    llm: ChatLLM = Depends(get_llm),
) -> ChatResponse:
    ticket: Ticket | None = None
    if body.ticket_id:
        ticket = db.get(Ticket, body.ticket_id)
        if ticket is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        if user.role != UserRole.admin and ticket.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
        db.add(
            Message(
                ticket_id=ticket.id,
                role=MessageRole.user,
                content=body.message,
            )
        )

    settings = get_settings()
    result = run_support_agent(
        question=body.message,
        user_id=user.id,
        user_role=user.role.value,
        store=store,
        embedder=embedder,
        llm=llm,
        db=db,
        ticket_id=body.ticket_id,
        settings=settings,
    )

    if ticket is not None:
        # Persist classification onto the ticket for triage.
        ticket.category = result.category
        try:
            ticket.priority = TicketPriority(result.priority)
            ticket.urgency = TicketUrgency(result.urgency)
        except ValueError:
            pass
        # Avoid duplicating draft messages already written by the draft tool.
        if "create_draft_response" not in result.tools_used:
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.assistant,
                    content=result.answer,
                )
            )
        if result.status == AnswerStatus.escalated.value:
            ticket.status = TicketStatus.escalated

    db.add(
        AuditLog(
            user_id=user.id,
            action="chat.agent",
            resource_type="ticket" if ticket else "chat",
            resource_id=ticket.id if ticket else None,
            detail={
                "status": result.status,
                "escalation_reason": result.escalation_reason,
                "citation_count": len(result.citations),
                "retrieval_hit_count": result.retrieval_hit_count,
                "top_score": result.top_score,
                "category": result.category,
                "priority": result.priority,
                "urgency": result.urgency,
                "tools_used": result.tools_used,
                "trace": result.trace,
            },
        )
    )
    db.flush()

    logger.info(
        "chat_agent_completed",
        extra={
            "status": result.status,
            "trace": result.trace,
            "user_id": user.id,
        },
    )

    return ChatResponse(
        status=result.status,
        answer=result.answer,
        citations=[CitationOut(**c) for c in result.citations],
        escalation_reason=result.escalation_reason,
        retrieval_hit_count=result.retrieval_hit_count,
        top_score=result.top_score,
        ticket_id=ticket.id if ticket else result.ticket_id,
        category=result.category,
        priority=result.priority,
        urgency=result.urgency,
        tools_used=result.tools_used,
        tool_result=result.tool_result,
        trace=result.trace,
    )
