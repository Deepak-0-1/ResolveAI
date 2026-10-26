"""Grounded RAG answering with citation validation and escalation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from resolveai_common.settings import Settings, get_settings
from resolveai_rag.embeddings import Embedder
from resolveai_rag.llm import ChatLLM
from resolveai_rag.store import SearchHit, VectorStore

SYSTEM_PROMPT = """You are ResolveAI, a customer support assistant for NovaDesk.
Answer ONLY using the numbered sources provided.
Rules:
- If the sources do not contain the answer, say you do not have enough information.
- Cite sources inline using [1], [2], etc. matching the source numbers.
- Do not invent policies, prices, or procedures not present in the sources.
- Be concise and helpful.
"""


class AnswerStatus(StrEnum):
    answered = "answered"
    escalated = "escalated"
    refused = "refused"


@dataclass
class Citation:
    index: int
    chunk_id: str
    document_id: str
    title: str | None
    filename: str | None
    snippet: str
    score: float


@dataclass
class GroundedAnswer:
    status: AnswerStatus
    answer: str
    citations: list[Citation] = field(default_factory=list)
    escalation_reason: str | None = None
    retrieval_hit_count: int = 0
    top_score: float | None = None


def answer_question(
    *,
    question: str,
    store: VectorStore,
    embedder: Embedder,
    llm: ChatLLM,
    settings: Settings | None = None,
) -> GroundedAnswer:
    cfg = settings or get_settings()
    q = question.strip()
    if not q:
        return GroundedAnswer(
            status=AnswerStatus.refused,
            answer="Please provide a question.",
            escalation_reason="empty_question",
        )

    sensitive = _match_sensitive(q, cfg.escalate_keyword_list)
    if sensitive:
        return GroundedAnswer(
            status=AnswerStatus.escalated,
            answer=(
                "This request needs a human specialist for security or account-ownership reasons. "
                "I am escalating it to our support team."
            ),
            escalation_reason=f"sensitive_topic:{sensitive}",
        )

    query_vec = embedder.embed([q])[0]
    use_hybrid = cfg.retrieval_mode.lower() == "hybrid"
    hits = store.search(
        query_vec,
        limit=cfg.retrieval_top_k,
        query=q if use_hybrid else None,
    )
    top_score = hits[0].score if hits else None

    if not hits:
        return GroundedAnswer(
            status=AnswerStatus.escalated,
            answer=(
                "I could not find relevant information in the knowledge base. "
                "Escalating to a human agent."
            ),
            escalation_reason="no_retrieval_hits",
            retrieval_hit_count=0,
            top_score=None,
        )

    # Keep only hits above the confidence floor.
    strong = [h for h in hits if h.score >= cfg.min_retrieval_score]
    if not strong:
        return GroundedAnswer(
            status=AnswerStatus.escalated,
            answer=(
                "I found only weak matches in the knowledge base and do not want to guess. "
                "Escalating to a human agent."
            ),
            escalation_reason="low_retrieval_score",
            retrieval_hit_count=len(hits),
            top_score=top_score,
        )

    user_prompt = _build_user_prompt(q, strong)
    raw = llm.complete(system=SYSTEM_PROMPT, user=user_prompt)
    citations = _extract_citations(raw, strong)

    if _looks_uninformed(raw) and not citations:
        return GroundedAnswer(
            status=AnswerStatus.refused,
            answer=raw,
            citations=[],
            escalation_reason="insufficient_grounding",
            retrieval_hit_count=len(hits),
            top_score=top_score,
        )

    return GroundedAnswer(
        status=AnswerStatus.answered,
        answer=raw,
        citations=citations,
        retrieval_hit_count=len(hits),
        top_score=top_score,
    )


def _match_sensitive(question: str, keywords: list[str]) -> str | None:
    lowered = question.lower()
    for keyword in keywords:
        if keyword and keyword in lowered:
            return keyword
    return None


def _build_user_prompt(question: str, hits: list[SearchHit]) -> str:
    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        title = hit.payload.get("title") or hit.payload.get("filename") or "source"
        blocks.append(f"Source [{i}] ({title}):\n{hit.text}")
    joined = "\n\n".join(blocks)
    return f"Question: {question}\n\nSources:\n{joined}\n\nAnswer with citations:"


def _extract_citations(answer: str, hits: list[SearchHit]) -> list[Citation]:
    cited_indexes = sorted({int(m) for m in re.findall(r"\[(\d+)\]", answer)})
    citations: list[Citation] = []
    for idx in cited_indexes:
        if idx < 1 or idx > len(hits):
            continue
        hit = hits[idx - 1]
        citations.append(
            Citation(
                index=idx,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                title=hit.payload.get("title"),
                filename=hit.payload.get("filename"),
                snippet=hit.text[:280],
                score=hit.score,
            )
        )
    return citations


def _looks_uninformed(answer: str) -> bool:
    lowered = answer.lower()
    markers = [
        "do not have enough information",
        "don't have enough information",
        "not enough information",
        "cannot find",
        "can't find",
        "no information",
    ]
    return any(m in lowered for m in markers)
