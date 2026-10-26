"""Knowledge-base upload, list, and dense search endpoints."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from resolveai_api.deps import get_current_user, require_roles
from resolveai_api.rag_deps import get_embedder, get_vector_store
from resolveai_api.schemas import DocumentOut, SearchHitOut, SearchRequest, SearchResponse
from resolveai_common.settings import get_settings
from resolveai_db.models import (
    AuditLog,
    DocumentStatus,
    KnowledgeDocument,
    User,
    UserRole,
)
from resolveai_db.session import get_db
from resolveai_rag.embeddings import Embedder
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.parsing import detect_source_type
from resolveai_rag.store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kb", tags=["knowledge-base"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> KnowledgeDocument:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    try:
        detect_source_type(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    settings = get_settings()
    doc_id = str(uuid.uuid4())
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    storage_path = upload_root / f"{doc_id}_{Path(file.filename).name}"
    storage_path.write_bytes(data)

    doc = KnowledgeDocument(
        id=doc_id,
        filename=file.filename,
        title=Path(file.filename).stem,
        source_type=detect_source_type(file.filename),
        status=DocumentStatus.pending,
        storage_path=str(storage_path),
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()

    try:
        result = ingest_bytes(
            document_id=doc.id,
            filename=file.filename,
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
        doc.doc_metadata = {"preview": result.text_preview}
    except Exception as exc:  # noqa: BLE001
        logger.exception("kb_ingest_failed", extra={"document_id": doc.id})
        doc.status = DocumentStatus.failed
        doc.error_message = str(exc)
        db.add(
            AuditLog(
                user_id=user.id,
                action="kb.ingest_failed",
                resource_type="knowledge_document",
                resource_id=doc.id,
                detail={"error": str(exc)},
            )
        )
        db.flush()
        raise HTTPException(status_code=502, detail=f"Ingest failed: {exc}") from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="kb.upload",
            resource_type="knowledge_document",
            resource_id=doc.id,
            detail={"filename": doc.filename, "chunks": doc.chunk_count},
        )
    )
    db.flush()
    return doc


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.admin)),
) -> list[KnowledgeDocument]:
    return list(db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all())


@router.post("/search", response_model=SearchResponse)
def search_kb(
    body: SearchRequest,
    _user: User = Depends(get_current_user),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> SearchResponse:
    settings = get_settings()
    vectors = embedder.embed([body.query])
    hits = store.search(
        vectors[0],
        limit=body.limit,
        query=body.query if settings.retrieval_mode.lower() == "hybrid" else None,
    )
    return SearchResponse(
        query=body.query,
        hits=[
            SearchHitOut(
                chunk_id=h.chunk_id,
                score=h.score,
                text=h.text,
                document_id=h.document_id,
                chunk_index=h.chunk_index,
                filename=h.payload.get("filename"),
                title=h.payload.get("title"),
                source_type=h.payload.get("source_type"),
            )
            for h in hits
        ],
    )
