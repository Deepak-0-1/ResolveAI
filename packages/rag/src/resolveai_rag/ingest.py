"""End-to-end ingest: parse → chunk → embed → upsert."""

from __future__ import annotations

from dataclasses import dataclass

from resolveai_common.settings import Settings, get_settings
from resolveai_rag.chunking import chunk_document
from resolveai_rag.embeddings import Embedder, OllamaEmbedder
from resolveai_rag.parsing import parse_bytes
from resolveai_rag.store import VectorStore


@dataclass
class IngestResult:
    title: str
    source_type: str
    chunk_count: int
    point_ids: list[str]
    text_preview: str


def ingest_bytes(
    *,
    document_id: str,
    filename: str,
    data: bytes,
    store: VectorStore,
    embedder: Embedder | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    cfg = settings or get_settings()
    emb = embedder or OllamaEmbedder(cfg)
    parsed = parse_bytes(filename, data)
    chunks = chunk_document(
        parsed,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )
    if not chunks:
        raise ValueError("No chunks produced from document")

    store.ensure_collection(emb.dimensions)
    store.delete_by_document(document_id)
    vectors = emb.embed([c.text for c in chunks])
    point_ids = store.upsert_chunks(
        document_id=document_id,
        chunks=chunks,
        vectors=vectors,
        filename=filename,
    )
    return IngestResult(
        title=parsed.title,
        source_type=parsed.source_type,
        chunk_count=len(chunks),
        point_ids=point_ids,
        text_preview=parsed.text[:240],
    )
