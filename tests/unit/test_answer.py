from resolveai_common.settings import Settings
from resolveai_rag.answer import AnswerStatus, answer_question
from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.llm import FakeLLM
from resolveai_rag.store import InMemoryVectorStore


def _ready_store() -> tuple[InMemoryVectorStore, HashEmbedder]:
    store = InMemoryVectorStore()
    embedder = HashEmbedder(32)
    ingest_bytes(
        document_id="doc-pw",
        filename="password.txt",
        data=(
            b"To reset a NovaDesk password, click Forgot password on the login page. "
            b"The reset link expires in 30 minutes."
        ),
        store=store,
        embedder=embedder,
    )
    return store, embedder


def test_grounded_answer_with_citation() -> None:
    store, embedder = _ready_store()
    settings = Settings(min_retrieval_score=0.01, retrieval_top_k=3)
    result = answer_question(
        question="How do I reset my password?",
        store=store,
        embedder=embedder,
        llm=FakeLLM(),
        settings=settings,
    )
    assert result.status == AnswerStatus.answered
    assert result.citations
    assert result.citations[0].document_id == "doc-pw"
    assert "[1]" in result.answer


def test_escalates_on_sensitive_topic() -> None:
    store, embedder = _ready_store()
    settings = Settings(min_retrieval_score=0.01)
    result = answer_question(
        question="Please disable MFA on my account now",
        store=store,
        embedder=embedder,
        llm=FakeLLM(),
        settings=settings,
    )
    assert result.status == AnswerStatus.escalated
    assert result.escalation_reason and "sensitive" in result.escalation_reason


def test_escalates_when_no_hits() -> None:
    store = InMemoryVectorStore()
    embedder = HashEmbedder(32)
    settings = Settings(min_retrieval_score=0.01)
    result = answer_question(
        question="Anything about billing?",
        store=store,
        embedder=embedder,
        llm=FakeLLM(),
        settings=settings,
    )
    assert result.status == AnswerStatus.escalated
    assert result.escalation_reason == "no_retrieval_hits"
