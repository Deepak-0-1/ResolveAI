from resolveai_rag.bm25 import BM25Index, reciprocal_rank_fusion, tokenize
from resolveai_rag.embeddings import HashEmbedder
from resolveai_rag.hybrid import HybridVectorStore
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.store import InMemoryVectorStore


def test_tokenize_and_bm25_ranks_exact_terms() -> None:
    assert "password" in tokenize("Reset your PASSWORD now")
    index = BM25Index()
    index.rebuild(
        {
            "a": "NovaDesk password reset link expires in 30 minutes",
            "b": "Billing invoices are available as PDF downloads",
        }
    )
    hits = index.search("password reset", limit=2)
    assert hits
    assert hits[0][0] == "a"


def test_rrf_prefers_agreement() -> None:
    fused = reciprocal_rank_fusion(
        [["doc1", "doc2"], ["doc1", "doc3"]],
        k=60,
        limit=3,
    )
    assert fused[0][0] == "doc1"


def test_hybrid_surfaces_keyword_match() -> None:
    inner = InMemoryVectorStore()
    store = HybridVectorStore(inner, rrf_k=60)
    embedder = HashEmbedder(32)
    ingest_bytes(
        document_id="d1",
        filename="billing.txt",
        data=b"Refunds for unused prepaid months may be issued within 14 days of renewal.",
        store=store,
        embedder=embedder,
    )
    ingest_bytes(
        document_id="d2",
        filename="password.txt",
        data=b"Click Forgot password on the login page to reset access.",
        store=store,
        embedder=embedder,
    )
    query = "refunds within 14 days"
    vector = embedder.embed([query])[0]
    hits = store.search(vector, limit=2, query=query)
    assert hits
    assert "refund" in hits[0].text.lower() or "14" in hits[0].text.lower()
