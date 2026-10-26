"""Qdrant vector store wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from resolveai_common.settings import Settings, get_settings
from resolveai_rag.types import Chunk


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    text: str
    document_id: str
    chunk_index: int
    payload: dict[str, Any]


class VectorStore:
    def ensure_collection(self, dimensions: int) -> None: ...

    def upsert_chunks(
        self,
        *,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        filename: str,
    ) -> list[str]: ...

    def delete_by_document(self, document_id: str) -> None: ...

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 5,
        query: str | None = None,
    ) -> list[SearchHit]: ...


class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        settings: Settings | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or QdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port,
            timeout=self.settings.http_timeout_seconds,
            check_compatibility=False,
        )
        self.collection = self.settings.qdrant_collection

    def ensure_collection(self, dimensions: int) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection in existing:
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(
                size=dimensions,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        *,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        filename: str,
    ) -> list[str]:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        points: list[qmodels.PointStruct] = []
        ids: list[str] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid4())
            ids.append(point_id)
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "filename": filename,
                        "title": chunk.metadata.get("title"),
                        "source_type": chunk.metadata.get("source_type"),
                    },
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection, points=points)
        return ids

    def delete_by_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 5,
        query: str | None = None,
    ) -> list[SearchHit]:
        # Dense-only here; HybridVectorStore adds BM25+RRF when enabled.
        # qdrant-client >=1.12 uses query_points (`.search` was removed in 1.20).
        _ = query
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for point in response.points:
            payload = dict(point.payload or {})
            hits.append(
                SearchHit(
                    chunk_id=str(point.id),
                    score=float(point.score or 0.0),
                    text=str(payload.get("text", "")),
                    document_id=str(payload.get("document_id", "")),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    payload=payload,
                )
            )
        return hits


class InMemoryVectorStore(VectorStore):
    """Test double — no Qdrant required."""

    def __init__(self) -> None:
        self.points: list[dict[str, Any]] = []
        self.dimensions: int | None = None

    def ensure_collection(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def upsert_chunks(
        self,
        *,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        filename: str,
    ) -> list[str]:
        ids: list[str] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid4())
            ids.append(point_id)
            self.points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "document_id": document_id,
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "filename": filename,
                        "title": chunk.metadata.get("title"),
                        "source_type": chunk.metadata.get("source_type"),
                    },
                }
            )
        return ids

    def delete_by_document(self, document_id: str) -> None:
        self.points = [p for p in self.points if p["payload"]["document_id"] != document_id]

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 5,
        query: str | None = None,
    ) -> list[SearchHit]:
        _ = query
        scored: list[tuple[float, dict[str, Any]]] = []
        for point in self.points:
            score = _cosine(vector, point["vector"])
            scored.append((score, point))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: list[SearchHit] = []
        for score, point in scored[:limit]:
            payload = point["payload"]
            hits.append(
                SearchHit(
                    chunk_id=point["id"],
                    score=score,
                    text=payload["text"],
                    document_id=payload["document_id"],
                    chunk_index=payload["chunk_index"],
                    payload=payload,
                )
            )
        return hits


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return dot / (na * nb)
