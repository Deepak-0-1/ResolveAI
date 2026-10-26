from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.store import InMemoryVectorStore


def test_ingest_roundtrip_search() -> None:
    store = InMemoryVectorStore()
    embedder = HashEmbedder(dimensions=32)
    data = (
        b"NovaDesk password reset: use Forgot password on the login page. "
        b"The reset link expires in 30 minutes."
    )
    result = ingest_bytes(
        document_id="doc-1",
        filename="account.txt",
        data=data,
        store=store,
        embedder=embedder,
    )
    assert result.chunk_count >= 1
    assert len(result.point_ids) == result.chunk_count

    query_vec = embedder.embed(["How do I reset my password?"])[0]
    hits = store.search(query_vec, limit=3)
    assert hits
    assert hits[0].document_id == "doc-1"
    assert "password" in hits[0].text.lower()
