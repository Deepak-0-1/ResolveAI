"""User feedback on answers (thumbs up/down)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from resolveai_api.deps import get_current_user
from resolveai_api.schemas import FeedbackCreate, FeedbackOut
from resolveai_db.models import AuditLog, Feedback, Ticket, User, UserRole
from resolveai_db.session import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def create_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Feedback:
    if body.rating not in (-1, 1):
        raise HTTPException(status_code=400, detail="rating must be 1 or -1")

    if body.ticket_id:
        ticket = db.get(Ticket, body.ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if user.role != UserRole.admin and ticket.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your ticket")

    row = Feedback(
        user_id=user.id,
        ticket_id=body.ticket_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(row)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="feedback.create",
            resource_type="feedback",
            resource_id=row.id,
            detail={"rating": body.rating},
        )
    )
    db.flush()
    return row
