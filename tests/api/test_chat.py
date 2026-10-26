from resolveai_api.rag_deps import (
    get_embedder,
    get_llm,
    get_vector_store,
    set_embedder,
    set_llm,
    set_vector_store,
)
from resolveai_common.settings import get_settings
from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.llm import FakeLLM
from resolveai_rag.store import InMemoryVectorStore


def _login(client, email: str = "user@example.com", password: str = "password123") -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "User"},
    )
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_chat_returns_citations(client, monkeypatch) -> None:
    monkeypatch.setenv("MIN_RETRIEVAL_SCORE", "0.01")
    get_settings.cache_clear()

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
    llm = FakeLLM()
    set_vector_store(store)
    set_embedder(embedder)
    set_llm(llm)
    client.app.dependency_overrides[get_vector_store] = lambda: store
    client.app.dependency_overrides[get_embedder] = lambda: embedder
    client.app.dependency_overrides[get_llm] = lambda: llm

    try:
        token = _login(client)
        response = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "How do I reset my NovaDesk password?"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "answered"
        assert body["citations"]
        assert body["citations"][0]["document_id"] == "doc-1"
        assert body["category"] == "account"
        assert "classify" in body["trace"]
    finally:
        client.app.dependency_overrides.pop(get_vector_store, None)
        client.app.dependency_overrides.pop(get_embedder, None)
        client.app.dependency_overrides.pop(get_llm, None)
        set_vector_store(None)
        set_embedder(None)
        set_llm(None)
        get_settings.cache_clear()


def test_chat_escalates_sensitive(client, monkeypatch) -> None:
    monkeypatch.setenv("MIN_RETRIEVAL_SCORE", "0.01")
    get_settings.cache_clear()

    store = InMemoryVectorStore()
    embedder = HashEmbedder(32)
    set_vector_store(store)
    set_embedder(embedder)
    set_llm(FakeLLM())
    client.app.dependency_overrides[get_vector_store] = lambda: store
    client.app.dependency_overrides[get_embedder] = lambda: embedder
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM()

    try:
        token = _login(client, "s@example.com")
        response = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Please delete workspace immediately"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "escalated"
    finally:
        client.app.dependency_overrides.pop(get_vector_store, None)
        client.app.dependency_overrides.pop(get_embedder, None)
        client.app.dependency_overrides.pop(get_llm, None)
        set_vector_store(None)
        set_embedder(None)
        set_llm(None)
        get_settings.cache_clear()
