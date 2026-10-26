"""RAG package: parse, chunk, embed, and store knowledge-base documents."""

from resolveai_rag.types import Chunk, ParsedDocument

__all__ = ["Chunk", "IngestResult", "ParsedDocument", "ingest_bytes"]


def __getattr__(name: str):
    if name in {"IngestResult", "ingest_bytes"}:
        from resolveai_rag.ingest import IngestResult, ingest_bytes

        return IngestResult if name == "IngestResult" else ingest_bytes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
