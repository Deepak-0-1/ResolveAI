"""Seed demo users and sample tickets. Safe to re-run (upsert by email)."""

from __future__ import annotations

import logging

from resolveai_db.models import (
    Message,
    MessageRole,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketUrgency,
    User,
    UserRole,
)
from resolveai_db.security import hash_password
from resolveai_db.session import get_engine, get_session_factory, session_scope

logger = logging.getLogger(__name__)

SEED_USERS = [
    {
        "email": "admin@resolveai.local",
        "password": "admin123!",
        "full_name": "ResolveAI Admin",
        "role": UserRole.admin,
    },
    {
        "email": "customer@resolveai.local",
        "password": "customer123!",
        "full_name": "Demo Customer",
        "role": UserRole.customer,
    },
]


def seed(*, database_url: str | None = None) -> None:
    if database_url:
        engine = get_engine(database_url)
        factory = get_session_factory(engine)
    else:
        factory = get_session_factory()

    with session_scope(factory) as session:
        users_by_email: dict[str, User] = {}
        for item in SEED_USERS:
            user = session.query(User).filter(User.email == item["email"]).one_or_none()
            if user is None:
                user = User(
                    email=item["email"],
                    hashed_password=hash_password(item["password"]),
                    full_name=item["full_name"],
                    role=item["role"],
                )
                session.add(user)
                session.flush()
                logger.info("seeded_user", extra={"email": item["email"]})
            users_by_email[item["email"]] = user

        customer = users_by_email["customer@resolveai.local"]
        existing = (
            session.query(Ticket)
            .filter(Ticket.user_id == customer.id, Ticket.subject == "Cannot reset password")
            .one_or_none()
        )
        if existing is None:
            ticket = Ticket(
                user_id=customer.id,
                subject="Cannot reset password",
                status=TicketStatus.open,
                category="account",
                priority=TicketPriority.medium,
                urgency=TicketUrgency.medium,
            )
            session.add(ticket)
            session.flush()
            session.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.user,
                    content="I never receive the password reset email.",
                )
            )
            logger.info("seeded_ticket", extra={"ticket_id": ticket.id})


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    seed()
    print(
        "Seed complete: admin@resolveai.local / admin123! ; customer@resolveai.local / customer123!"
    )


if __name__ == "__main__":
    main()
