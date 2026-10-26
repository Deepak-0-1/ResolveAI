from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from resolveai_agent.classify import classify_message
from resolveai_agent.graph import run_support_agent
from resolveai_agent.tools import detect_tool_intent
from resolveai_common.settings import Settings
from resolveai_db.models import Base, Ticket, TicketPriority, TicketUrgency, User, UserRole
from resolveai_db.security import hash_password
from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.llm import FakeLLM
from resolveai_rag.store import InMemoryVectorStore


def test_classify_billing_urgent() -> None:
    result = classify_message("Urgent: my invoice payment failed")
    assert result.category == "billing"
    assert result.priority in {"high", "critical"}
    assert result.urgency == "high"


def test_detect_tool_intent() -> None:
    assert detect_tool_intent("What is the ticket status for abc?") == "get_ticket_status"
    assert detect_tool_intent("Please draft a reply for this ticket") == "create_draft_response"
    assert detect_tool_intent("How do I reset my password?") is None


def test_graph_answers_with_trace() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()

    user = User(
        email="u@example.com",
        hashed_password=hash_password("password123"),
        full_name="U",
        role=UserRole.customer,
    )
    session.add(user)
    session.commit()

    store = InMemoryVectorStore()
    embedder = HashEmbedder(32)
    ingest_bytes(
        document_id="doc-1",
        filename="password.txt",
        data=(
            b"To reset a NovaDesk password, click Forgot password on the login page. "
            b"The reset link expires in 30 minutes."
        ),
        store=store,
        embedder=embedder,
    )

    result = run_support_agent(
        question="How do I reset my password?",
        user_id=user.id,
        user_role=user.role.value,
        store=store,
        embedder=embedder,
        llm=FakeLLM(),
        db=session,
        settings=Settings(min_retrieval_score=0.01),
    )
    assert result.status == "answered"
    assert result.category == "account"
    assert "classify" in result.trace
    assert any(t.startswith("retrieve_answer") for t in result.trace)
    session.close()


def test_graph_ticket_status_tool() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()

    user = User(
        email="u2@example.com",
        hashed_password=hash_password("password123"),
        full_name="U2",
        role=UserRole.customer,
    )
    session.add(user)
    session.flush()
    ticket = Ticket(
        user_id=user.id,
        subject="Help",
        priority=TicketPriority.high,
        urgency=TicketUrgency.high,
    )
    session.add(ticket)
    session.commit()

    result = run_support_agent(
        question=f"What is the ticket status for {ticket.id}?",
        user_id=user.id,
        user_role=user.role.value,
        store=InMemoryVectorStore(),
        embedder=HashEmbedder(32),
        llm=FakeLLM(),
        db=session,
        settings=Settings(min_retrieval_score=0.01),
    )
    assert result.status == "answered"
    assert "get_ticket_status" in result.tools_used
    assert result.tool_result and result.tool_result.get("ok") is True
    session.close()
