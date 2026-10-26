"""Ticket CRUD plus explicit tool endpoints (status / draft)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from resolveai_agent.tools import create_draft_response, get_ticket_status
from resolveai_api.deps import get_current_user
from resolveai_api.schemas import (
    DraftCreate,
    DraftOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketStatusOut,
)
from resolveai_db.models import (
    AuditLog,
    Message,
    MessageRole,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from resolveai_db.session import get_db

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_accessible_ticket(db: Session, ticket_id: str, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if user.role != UserRole.admin and ticket.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
    return ticket


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Ticket:
    ticket = Ticket(
        user_id=user.id,
        subject=body.subject,
        category=body.category,
        priority=body.priority,
        urgency=body.urgency,
    )
    db.add(ticket)
    db.flush()
    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.user,
            content=body.body,
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="ticket.create",
            resource_type="ticket",
            resource_id=ticket.id,
            detail={"subject": ticket.subject},
        )
    )
    db.flush()
    return ticket


@router.get("", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
) -> list[Ticket]:
    query = db.query(Ticket).order_by(Ticket.created_at.desc())
    if user.role != UserRole.admin:
        query = query.filter(Ticket.user_id == user.id)
    if status_filter is not None:
        query = query.filter(Ticket.status == status_filter)
    return list(query.all())


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket_detail(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages))
        .filter(Ticket.id == ticket_id)
        .one_or_none()
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if user.role != UserRole.admin and ticket.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
    return ticket


@router.get(
    "/{ticket_id}/status",
    response_model=TicketStatusOut,
    summary="Tool: get ticket status",
)
def ticket_status(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketStatusOut:
    """Explicit tool endpoint used by agents and the admin UI."""
    result = get_ticket_status(
        db,
        ticket_id,
        user_id=user.id,
        user_role=user.role.value,
    )
    if not result.get("ok"):
        error = result.get("error")
        if error == "ticket_not_found":
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=403, detail="Not your ticket")

    ticket = _get_accessible_ticket(db, ticket_id, user)
    db.add(
        AuditLog(
            user_id=user.id,
            action="tool.get_ticket_status",
            resource_type="ticket",
            resource_id=ticket_id,
        )
    )
    db.flush()
    return TicketStatusOut(
        ticket_id=ticket.id,
        status=ticket.status,
        priority=ticket.priority,
        urgency=ticket.urgency,
        category=ticket.category,
        subject=ticket.subject,
    )


@router.post(
    "/{ticket_id}/draft",
    response_model=DraftOut,
    summary="Tool: create draft response (does not send)",
)
def create_ticket_draft(
    ticket_id: str,
    body: DraftCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DraftOut:
    """Store a draft reply on the ticket. Never sends email or notifies the customer."""
    result = create_draft_response(
        db,
        ticket_id,
        body.body,
        user_id=user.id,
        user_role=user.role.value,
    )
    if not result.get("ok"):
        error = result.get("error")
        if error == "ticket_not_found":
            raise HTTPException(status_code=404, detail="Ticket not found")
        raise HTTPException(status_code=403, detail="Not your ticket")

    db.add(
        AuditLog(
            user_id=user.id,
            action="tool.create_draft_response",
            resource_type="ticket",
            resource_id=ticket_id,
            detail={"sent": False},
        )
    )
    db.flush()
    return DraftOut(
        ticket_id=result["ticket_id"],
        draft_preview=result["draft_preview"],
        sent=False,
        note=result.get("note", "Draft stored only; no external send."),
    )
