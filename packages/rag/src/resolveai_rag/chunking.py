"""Simple overlapping character chunker with paragraph awareness."""

from __future__ import annotations

from resolveai_rag.types import Chunk, ParsedDocument


def chunk_document(
    document: ParsedDocument,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    text = document.text.strip()
    if not text:
        return []

    # Prefer splitting on blank lines so FAQ pairs / sections stay together when possible.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    pieces: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            pieces.extend(_split_long(para, chunk_size, chunk_overlap))
            continue
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            pieces.append(buffer)
            buffer = para
    if buffer:
        pieces.append(buffer)

    chunks: list[Chunk] = []
    for index, piece in enumerate(pieces):
        chunks.append(
            Chunk(
                text=piece,
                index=index,
                metadata={
                    "title": document.title,
                    "source_type": document.source_type,
                    **document.metadata,
                },
            )
        )
    return chunks


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return parts
