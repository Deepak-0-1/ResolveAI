"""Injectable RAG dependencies (swap embedder/store/llm in tests)."""

from __future__ import annotations

from resolveai_common.settings import get_settings
from resolveai_rag.embeddings import Embedder, OllamaEmbedder
from resolveai_rag.hybrid import maybe_wrap_hybrid
from resolveai_rag.llm import ChatLLM, OllamaChatLLM
from resolveai_rag.store import QdrantVectorStore, VectorStore

_embedder: Embedder | None = None
_store: VectorStore | None = None
_llm: ChatLLM | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbedder(get_settings())
    return _embedder


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        settings = get_settings()
        base = QdrantVectorStore(settings)
        _store = maybe_wrap_hybrid(
            base,
            enabled=settings.retrieval_mode.lower() == "hybrid",
            rrf_k=settings.hybrid_rrf_k,
        )
    return _store


def get_llm() -> ChatLLM:
    global _llm
    if _llm is None:
        _llm = OllamaChatLLM(get_settings())
    return _llm


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder


def set_vector_store(store: VectorStore | None) -> None:
    global _store
    _store = store


def set_llm(llm: ChatLLM | None) -> None:
    global _llm
    _llm = llm
