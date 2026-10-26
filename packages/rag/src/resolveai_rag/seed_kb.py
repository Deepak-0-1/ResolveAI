"""Seed synthetic NovaDesk KB files into Postgres + Qdrant."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from resolveai_common.settings import get_settings
from resolveai_db.models import DocumentStatus, KnowledgeDocument, User, UserRole
from resolveai_db.session import get_session_factory, session_scope
from resolveai_rag.embeddings import OllamaEmbedder
from resolveai_rag.hybrid import maybe_wrap_hybrid
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.store import QdrantVectorStore

logger = logging.getLogger(__name__)

DEFAULT_KB_DIR = Path("data/kb")


def seed_kb(kb_dir: Path | None = None) -> int:
    settings = get_settings()
    root = kb_dir or DEFAULT_KB_DIR
    if not root.exists():
        raise FileNotFoundError(f"KB directory not found: {root}")

    allowed = {".txt", ".json", ".faq", ".pdf", ".docx"}
    files = sorted(
        p
        for p in root.iterdir()
        if p.is_file() and (p.suffix.lower() in allowed or p.name.lower().endswith(".faq.txt"))
    )
    if not files:
        raise FileNotFoundError(f"No KB files in {root}")

    store = maybe_wrap_hybrid(
        QdrantVectorStore(settings),
        enabled=settings.retrieval_mode.lower() == "hybrid",
        rrf_k=settings.hybrid_rrf_k,
    )
    embedder = OllamaEmbedder(settings)
    indexed = 0

    with session_scope() as session:
        admin = (
            session.query(User)
            .filter(User.role == UserRole.admin)
            .order_by(User.created_at.asc())
            .first()
        )
        admin_id = admin.id if admin else None

        for path in files:
            existing = (
                session.query(KnowledgeDocument)
                .filter(KnowledgeDocument.filename == path.name)
                .one_or_none()
            )
            if existing and existing.status == DocumentStatus.indexed:
                logger.info("skip_existing", extra={"filename": path.name})
                continue

            doc_id = existing.id if existing else str(uuid.uuid4())
            data = path.read_bytes()
            if existing is None:
                doc = KnowledgeDocument(
                    id=doc_id,
                    filename=path.name,
                    title=path.stem,
                    source_type="txt",
                    status=DocumentStatus.pending,
                    uploaded_by=admin_id,
                    storage_path=str(path),
                )
                session.add(doc)
                session.flush()
            else:
                doc = existing

            try:
                result = ingest_bytes(
                    document_id=doc.id,
                    filename=path.name,
                    data=data,
                    store=store,
                    embedder=embedder,
                    settings=settings,
                )
                doc.title = result.title
                doc.source_type = result.source_type
                doc.chunk_count = result.chunk_count
                doc.status = DocumentStatus.indexed
                doc.error_message = None
                indexed += 1
                logger.info(
                    "indexed_kb_file",
                    extra={"filename": path.name, "chunks": result.chunk_count},
                )
            except Exception as exc:  # noqa: BLE001
                doc.status = DocumentStatus.failed
                doc.error_message = str(exc)
                logger.exception("kb_seed_failed", extra={"filename": path.name})
                raise

    return indexed


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # Ensure factory uses settings URL
    get_session_factory()
    count = seed_kb()
    print(f"KB seed complete: indexed {count} file(s)")


if __name__ == "__main__":
    main()
