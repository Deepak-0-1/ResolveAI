from resolveai_api.rag_deps import get_embedder, get_vector_store, set_embedder, set_vector_store
from resolveai_db.models import User, UserRole
from resolveai_db.security import hash_password
from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.store import InMemoryVectorStore


def _login(client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_customer_cannot_upload(client) -> None:
    client.post(
        "/auth/register",
        json={"email": "cust@example.com", "password": "password123", "full_name": "C"},
    )
    token = _login(client, "cust@example.com", "password123")
    response = client.post(
        "/kb/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 403


def test_admin_upload_and_search(client, db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from resolveai_common.settings import get_settings

    get_settings.cache_clear()

    db_session.add(
        User(
            email="admin@example.com",
            hashed_password=hash_password("adminpass1"),
            full_name="Admin",
            role=UserRole.admin,
        )
    )
    db_session.commit()

    store = InMemoryVectorStore()
    embedder = HashEmbedder(32)
    set_vector_store(store)
    set_embedder(embedder)

    # Also override FastAPI deps on the live test app
    client.app.dependency_overrides[get_embedder] = lambda: embedder
    client.app.dependency_overrides[get_vector_store] = lambda: store

    try:
        token = _login(client, "admin@example.com", "adminpass1")
        content = (
            b"To reset a NovaDesk password, click Forgot password and check email. "
            b"Links expire after thirty minutes."
        )
        upload = client.post(
            "/kb/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("reset.txt", content, "text/plain")},
        )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["status"] == "indexed"
        assert body["chunk_count"] >= 1

        listed = client.get("/kb/documents", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        assert len(listed.json()) >= 1

        search = client.post(
            "/kb/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "password reset", "limit": 3},
        )
        assert search.status_code == 200, search.text
        hits = search.json()["hits"]
        assert hits
        assert "password" in hits[0]["text"].lower()
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)
        client.app.dependency_overrides.pop(get_vector_store, None)
        set_vector_store(None)
        set_embedder(None)
        get_settings.cache_clear()
