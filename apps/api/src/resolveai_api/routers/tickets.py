"""Ticket CRUD plus explicit tool endpoints (status / draft)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from resolveai_agent.tools import create_draft_response, get_ticket_status
from resolveai_api.deps import get_current_user
from resolveai_api.schemas import (
    DraftCreate,
    DraftOut,
    MessageCreate,
    MessageOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketStatusOut,
    TicketUpdate,
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


@router.patch("/{ticket_id}", response_model=TicketDetail)
def update_ticket(
    ticket_id: str,
    body: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Ticket:
    """Update ticket status, category, priority, or urgency.
    Admins can update any field. Customers can only close/resolve their own ticket.
    """
    ticket = _get_accessible_ticket(db, ticket_id, user)
    changes: dict[str, str] = {}

    if body.status is not None:
        if user.role != UserRole.admin and body.status not in (TicketStatus.closed, TicketStatus.resolved):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers may only close or resolve their own ticket",
            )
        ticket.status = body.status
        changes["status"] = body.status.value

    if body.category is not None:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff can reclassify tickets")
        ticket.category = body.category
        changes["category"] = body.category

    if body.priority is not None:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff can update priority")
        ticket.priority = body.priority
        changes["priority"] = body.priority.value

    if body.urgency is not None:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff can update urgency")
        ticket.urgency = body.urgency
        changes["urgency"] = body.urgency.value

    if changes:
        db.add(
            AuditLog(
                user_id=user.id,
                action="ticket.update",
                resource_type="ticket",
                resource_id=ticket.id,
                detail=changes,
            )
        )
        db.flush()

    return (
        db.query(Ticket)
        .options(joinedload(Ticket.messages))
        .filter(Ticket.id == ticket.id)
        .one()
    )


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def add_ticket_message(
    ticket_id: str,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    """Post a message to the ticket conversation.
    Customers post as user role; staff can post as agent or assistant.
    """
    ticket = _get_accessible_ticket(db, ticket_id, user)

    # Determine message role
    role = MessageRole.user
    if user.role == UserRole.admin:
        if body.role in (MessageRole.agent.value, MessageRole.assistant.value):
            role = MessageRole(body.role)
        else:
            role = MessageRole.agent

    msg = Message(
        ticket_id=ticket.id,
        role=role,
        content=body.content.strip(),
    )
    db.add(msg)

    # If staff replies to an escalated ticket, move to pending customer response
    if user.role == UserRole.admin and ticket.status == TicketStatus.escalated:
        ticket.status = TicketStatus.pending

    db.add(
        AuditLog(
            user_id=user.id,
            action="ticket.message.create",
            resource_type="ticket",
            resource_id=ticket.id,
            detail={"role": role.value, "length": len(body.content)},
        )
    )
    db.flush()
    return msg

