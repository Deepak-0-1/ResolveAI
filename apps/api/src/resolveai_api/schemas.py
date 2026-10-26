"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from resolveai_db.models import (
    DocumentStatus,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
    UserRole,
)


def _normalize_email(value: str) -> str:
    """Permissive email check — allows demo domains like *.local (EmailStr rejects them)."""
    email = value.strip().lower()
    if "@" not in email:
        raise ValueError("invalid email address")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise ValueError("invalid email address")
    if " " in email:
        raise ValueError("invalid email address")
    return email


EmailAddress = Annotated[str, AfterValidator(_normalize_email)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=200)


class UserLogin(BaseModel):
    email: EmailAddress
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailAddress
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=1, max_length=10_000)
    category: str | None = Field(default=None, max_length=100)
    priority: TicketPriority = TicketPriority.medium
    urgency: TicketUrgency = TicketUrgency.medium


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    subject: str
    status: TicketStatus
    category: str | None
    priority: TicketPriority
    urgency: TicketUrgency
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    role: str
    content: str
    created_at: datetime


class TicketDetail(TicketOut):
    messages: list[MessageOut] = Field(default_factory=list)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    title: str
    source_type: str
    status: DocumentStatus
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class SearchHitOut(BaseModel):
    chunk_id: str
    score: float
    text: str
    document_id: str
    chunk_index: int
    filename: str | None = None
    title: str | None = None
    source_type: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitOut]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    ticket_id: str | None = None


class CitationOut(BaseModel):
    index: int
    chunk_id: str
    document_id: str
    title: str | None = None
    filename: str | None = None
    snippet: str
    score: float


class ChatResponse(BaseModel):
    status: str
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    escalation_reason: str | None = None
    retrieval_hit_count: int = 0
    top_score: float | None = None
    ticket_id: str | None = None
    category: str | None = None
    priority: str | None = None
    urgency: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    tool_result: dict | None = None
    trace: list[str] = Field(default_factory=list)


class TicketStatusOut(BaseModel):
    ticket_id: str
    status: TicketStatus
    priority: TicketPriority
    urgency: TicketUrgency
    category: str | None = None
    subject: str


class DraftCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class DraftOut(BaseModel):
    ticket_id: str
    draft_preview: str
    sent: bool = False
    note: str = "Draft stored only; no external send."


class FeedbackCreate(BaseModel):
    rating: int = Field(description="1 = thumbs up, -1 = thumbs down")
    comment: str | None = Field(default=None, max_length=2000)
    ticket_id: str | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rating: int
    comment: str | None
    ticket_id: str | None
    created_at: datetime
