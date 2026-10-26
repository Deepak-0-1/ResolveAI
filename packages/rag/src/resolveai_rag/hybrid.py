"""Hybrid dense + BM25 retriever with Reciprocal Rank Fusion."""

from __future__ import annotations

from typing import Any

from resolveai_rag.bm25 import BM25Index, reciprocal_rank_fusion
from resolveai_rag.store import SearchHit, VectorStore
from resolveai_rag.types import Chunk


class HybridVectorStore(VectorStore):
    """
    Wraps any dense VectorStore and maintains a parallel BM25 corpus.
    When search(..., query=...) is provided, fuses dense + BM25 via RRF.
    """

    def __init__(self, inner: VectorStore, *, rrf_k: int = 60) -> None:
        self.inner = inner
        self.rrf_k = rrf_k
        self._texts: dict[str, str] = {}
        self._payloads: dict[str, dict[str, Any]] = {}
        self._bm25 = BM25Index()

    def ensure_collection(self, dimensions: int) -> None:
        self.inner.ensure_collection(dimensions)

    def upsert_chunks(
        self,
        *,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        filename: str,
    ) -> list[str]:
        # Remove prior chunks for this document from the sparse index.
        stale = [
            cid
            for cid, payload in self._payloads.items()
            if payload.get("document_id") == document_id
        ]
        for cid in stale:
            self._texts.pop(cid, None)
            self._payloads.pop(cid, None)

        ids = self.inner.upsert_chunks(
            document_id=document_id,
            chunks=chunks,
            vectors=vectors,
            filename=filename,
        )
        for point_id, chunk in zip(ids, chunks, strict=True):
            self._texts[point_id] = chunk.text
            self._payloads[point_id] = {
                "document_id": document_id,
                "chunk_index": chunk.index,
                "text": chunk.text,
                "filename": filename,
                "title": chunk.metadata.get("title"),
                "source_type": chunk.metadata.get("source_type"),
            }
        self._bm25.rebuild(self._texts)
        return ids

    def delete_by_document(self, document_id: str) -> None:
        self.inner.delete_by_document(document_id)
        stale = [
            cid
            for cid, payload in self._payloads.items()
            if payload.get("document_id") == document_id
        ]
        for cid in stale:
            self._texts.pop(cid, None)
            self._payloads.pop(cid, None)
        self._bm25.rebuild(self._texts)

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 5,
        query: str | None = None,
    ) -> list[SearchHit]:
        pool = max(limit * 3, limit)
        dense_hits = self.inner.search(vector, limit=pool)
        if not query:
            return dense_hits[:limit]

        sparse = self._bm25.search(query, limit=pool)
        dense_ids = [h.chunk_id for h in dense_hits]
        sparse_ids = [doc_id for doc_id, _ in sparse]
        fused = reciprocal_rank_fusion(
            [dense_ids, sparse_ids],
            k=self.rrf_k,
            limit=limit,
        )

        # Normalize RRF into ~[0, 1] so min_retrieval_score still applies.
        max_rrf = 2.0 / (self.rrf_k + 1)  # best case: rank-1 on both lists
        dense_by_id = {h.chunk_id: h for h in dense_hits}
        sparse_score = {doc_id: score for doc_id, score in sparse}
        hits: list[SearchHit] = []
        for doc_id, rrf_score in fused:
            norm = float(rrf_score) / max_rrf if max_rrf else float(rrf_score)
            if doc_id in dense_by_id:
                base = dense_by_id[doc_id]
                # Prefer the stronger of normalized RRF vs dense cosine for gating.
                score = max(norm, float(base.score))
                hits.append(
                    SearchHit(
                        chunk_id=base.chunk_id,
                        score=score,
                        text=base.text,
                        document_id=base.document_id,
                        chunk_index=base.chunk_index,
                        payload={
                            **base.payload,
                            "rrf_score": rrf_score,
                            "rrf_norm": norm,
                            "dense_score": base.score,
                            "retrieval": "hybrid",
                        },
                    )
                )
            elif doc_id in self._payloads:
                payload = self._payloads[doc_id]
                hits.append(
                    SearchHit(
                        chunk_id=doc_id,
                        score=norm,
                        text=str(payload.get("text", "")),
                        document_id=str(payload.get("document_id", "")),
                        chunk_index=int(payload.get("chunk_index", 0)),
                        payload={
                            **payload,
                            "rrf_score": rrf_score,
                            "rrf_norm": norm,
                            "bm25_score": sparse_score.get(doc_id),
                            "retrieval": "hybrid",
                        },
                    )
                )
        return hits


def maybe_wrap_hybrid(store: VectorStore, *, enabled: bool, rrf_k: int = 60) -> VectorStore:
    if not enabled:
        return store
    if isinstance(store, HybridVectorStore):
        return store
    return HybridVectorStore(store, rrf_k=rrf_k)


__all__ = ["HybridVectorStore", "maybe_wrap_hybrid"]
