"""
Repeatable baseline evaluation.

Default mode uses HashEmbedder + FakeLLM + in-memory store over data/kb
so CI can run without Ollama/Qdrant. Live mode (--live) uses configured
Ollama + Qdrant when available.

Never invent metrics — report only values computed from this run.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from resolveai_agent.graph import run_support_agent
from resolveai_common.settings import Settings
from resolveai_db.models import Base, User, UserRole
from resolveai_db.security import hash_password
from resolveai_rag.embeddings import HashEmbedder, OllamaEmbedder
from resolveai_rag.hybrid import HybridVectorStore
from resolveai_rag.ingest import ingest_bytes
from resolveai_rag.llm import OllamaChatLLM
from resolveai_rag.store import InMemoryVectorStore, QdrantVectorStore

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "eval" / "datasets" / "golden_v1.jsonl"
KB_DIR = ROOT / "data" / "kb"
REPORT_DIR = ROOT / "eval" / "reports"


class EvalFakeLLM:
    """Offline stand-in: quotes retrieved source text + [1], or refuses if empty."""

    def complete(self, *, system: str, user: str) -> str:
        if "Source [1]" not in user:
            return "I do not have enough information in the knowledge base to answer."
        start = user.find("Source [1]")
        chunk = user[start : start + 500]
        # Drop the header line for a cleaner answer preview
        body = chunk.split(":\n", 1)[-1].strip()
        if len(body) < 20:
            return "I do not have enough information in the knowledge base to answer."
        return f"Based on the knowledge base: {body[:280]} [1]"


@dataclass
class CaseResult:
    id: str
    kind: str
    expected_status: str
    actual_status: str
    status_match: bool
    latency_ms: float
    top_score: float | None
    retrieval_hit_count: int
    citation_count: int
    citations_valid: bool
    keyword_hit: bool | None
    forbidden_hit: bool
    escalation_match: bool | None
    retrieval_hint_hit: bool | None
    answer_preview: str
    errors: list[str] = field(default_factory=list)


def load_cases(path: Path = GOLDEN) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _index_kb(store: Any, embedder: Any) -> int:
    count = 0
    for path in sorted(KB_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".json", ".pdf", ".docx"} and not path.name.endswith(
            ".faq.txt"
        ):
            continue
        ingest_bytes(
            document_id=f"eval-{path.stem}",
            filename=path.name,
            data=path.read_bytes(),
            store=store,
            embedder=embedder,
            settings=Settings(
                chunk_size=500,
                chunk_overlap=80,
                embedding_dimensions=embedder.dimensions,
            ),
        )
        count += 1
    return count


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(n.lower() in lowered for n in needles)


def _citations_valid(citations: list[dict[str, Any]]) -> bool:
    if not citations:
        return True
    return all(
        c.get("chunk_id") and c.get("document_id") and isinstance(c.get("index"), int)
        for c in citations
    )


def evaluate_case(case: dict[str, Any], *, agent_kwargs: dict[str, Any]) -> CaseResult:
    started = time.perf_counter()
    errors: list[str] = []
    try:
        result = run_support_agent(question=case["question"], **agent_kwargs)
    except Exception as exc:  # noqa: BLE001
        latency = (time.perf_counter() - started) * 1000
        return CaseResult(
            id=case["id"],
            kind=case["kind"],
            expected_status=case["expected_status"],
            actual_status="error",
            status_match=False,
            latency_ms=latency,
            top_score=None,
            retrieval_hit_count=0,
            citation_count=0,
            citations_valid=False,
            keyword_hit=None,
            forbidden_hit=False,
            escalation_match=None,
            retrieval_hint_hit=None,
            answer_preview="",
            errors=[str(exc)],
        )

    latency = (time.perf_counter() - started) * 1000
    answer = result.answer or ""
    expected = case["expected_status"]
    actual = result.status

    # Missing/irrelevant: accept escalate OR refuse as correct non-answer.
    if case["kind"] in {"missing", "irrelevant"}:
        status_match = actual in {"escalated", "refused"}
    else:
        status_match = actual == expected

    must = case.get("must_include_any") or []
    keyword_hit: bool | None
    if must and actual == "answered":
        keyword_hit = _contains_any(answer, must)
    elif must and actual != "answered":
        keyword_hit = False
    else:
        keyword_hit = None

    forbidden = case.get("must_not_include") or []
    forbidden_hit = _contains_any(answer, forbidden) if forbidden else False

    esc_needle = case.get("escalation_contains")
    if esc_needle:
        escalation_match = actual == "escalated" and esc_needle in (result.escalation_reason or "")
    else:
        escalation_match = None

    hints = case.get("doc_hints") or []
    retrieval_hint_hit: bool | None = None
    if hints and result.citations:
        blob = " ".join(c.get("snippet", "") for c in result.citations).lower()
        retrieval_hint_hit = any(h.lower() in blob for h in hints)
    elif hints and result.retrieval_hit_count > 0:
        # No citations (tool/escalate path) — unknown
        retrieval_hint_hit = None

    if forbidden_hit:
        errors.append("forbidden_content")
    if keyword_hit is False and case["kind"] in {"normal", "paraphrase", "conflict"}:
        errors.append("missing_expected_keywords")

    return CaseResult(
        id=case["id"],
        kind=case["kind"],
        expected_status=expected,
        actual_status=actual,
        status_match=status_match and not forbidden_hit,
        latency_ms=latency,
        top_score=result.top_score,
        retrieval_hit_count=result.retrieval_hit_count,
        citation_count=len(result.citations),
        citations_valid=_citations_valid(result.citations),
        keyword_hit=keyword_hit,
        forbidden_hit=forbidden_hit,
        escalation_match=escalation_match,
        retrieval_hint_hit=retrieval_hint_hit,
        answer_preview=answer[:240],
        errors=errors,
    )


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    n = len(results)
    status_acc = sum(1 for r in results if r.status_match) / n if n else 0.0
    latencies = [r.latency_ms for r in results]
    by_kind: dict[str, dict[str, Any]] = {}
    for r in results:
        bucket = by_kind.setdefault(r.kind, {"n": 0, "status_match": 0})
        bucket["n"] += 1
        bucket["status_match"] += int(r.status_match)

    for _kind, bucket in by_kind.items():
        bucket["status_accuracy"] = bucket["status_match"] / bucket["n"]

    keyword_cases = [r for r in results if r.keyword_hit is not None]
    if keyword_cases:
        keyword_acc = sum(1 for r in keyword_cases if r.keyword_hit) / len(keyword_cases)
    else:
        keyword_acc = None
    esc_cases = [r for r in results if r.escalation_match is not None]
    esc_acc = (
        sum(1 for r in esc_cases if r.escalation_match) / len(esc_cases) if esc_cases else None
    )
    cite_valid = sum(1 for r in results if r.citations_valid) / n if n else 0.0

    return {
        "n_cases": n,
        "status_accuracy": round(status_acc, 4),
        "keyword_accuracy": None if keyword_acc is None else round(keyword_acc, 4),
        "escalation_accuracy": None if esc_acc is None else round(esc_acc, 4),
        "citation_validity": round(cite_valid, 4),
        "latency_ms_mean": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_ms_p50": round(statistics.median(latencies), 2) if latencies else None,
        "latency_ms_max": round(max(latencies), 2) if latencies else None,
        "by_kind": by_kind,
    }


def run_eval(
    *,
    live: bool = False,
    limit: int | None = None,
    retrieval_mode: str = "dense",
) -> dict[str, Any]:
    cases = load_cases()
    if limit is not None:
        cases = cases[:limit]

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    user = User(
        email="eval@resolveai.local",
        hashed_password=hash_password("eval-password"),
        full_name="Eval Runner",
        role=UserRole.customer,
    )
    session.add(user)
    session.commit()

    mode_prefix = "live" if live else "offline"
    if live:
        settings = Settings(
            min_retrieval_score=0.05,
            retrieval_top_k=5,
            retrieval_mode=retrieval_mode,
        )
        embedder = OllamaEmbedder(settings)
        base_store = QdrantVectorStore(settings)
        llm = OllamaChatLLM(settings)
    else:
        settings = Settings(
            min_retrieval_score=0.01,
            retrieval_top_k=5,
            embedding_dimensions=64,
            retrieval_mode=retrieval_mode,
        )
        embedder = HashEmbedder(64)
        base_store = InMemoryVectorStore()
        llm = EvalFakeLLM()

    store = (
        HybridVectorStore(base_store, rrf_k=settings.hybrid_rrf_k)
        if retrieval_mode.lower() == "hybrid"
        else base_store
    )
    mode = f"{mode_prefix}_{retrieval_mode}"

    docs_indexed = _index_kb(store, embedder)
    agent_kwargs = {
        "user_id": user.id,
        "user_role": user.role.value,
        "store": store,
        "embedder": embedder,
        "llm": llm,
        "db": session,
        "settings": settings,
    }

    results = [evaluate_case(case, agent_kwargs=agent_kwargs) for case in cases]
    summary = summarize(results)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "retrieval_mode": retrieval_mode,
        "docs_indexed": docs_indexed,
        "dataset": str(GOLDEN.relative_to(ROOT)),
        "summary": summary,
        "results": [asdict(r) for r in results],
        "notes": [
            "Metrics are from this run only — not fabricated.",
            "Offline mode uses HashEmbedder+FakeLLM; lexical/semantic quality is limited.",
            "Hybrid = dense + BM25 fused with Reciprocal Rank Fusion (RRF).",
            "Use --live with Ollama+Qdrant for stronger answer-quality measurement.",
        ],
    }
    session.close()
    return report


def _report_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# ResolveAI evaluation report ({report['mode']})",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Dataset: `{report['dataset']}` ({s['n_cases']} cases)",
        f"- Retrieval mode: `{report.get('retrieval_mode', 'dense')}`",
        f"- Docs indexed: `{report['docs_indexed']}`",
        "",
        "## Summary metrics (measured)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Status accuracy | {s['status_accuracy']} |",
        f"| Keyword accuracy | {s['keyword_accuracy']} |",
        f"| Escalation accuracy | {s['escalation_accuracy']} |",
        f"| Citation validity | {s['citation_validity']} |",
        f"| Latency mean (ms) | {s['latency_ms_mean']} |",
        f"| Latency p50 (ms) | {s['latency_ms_p50']} |",
        f"| Latency max (ms) | {s['latency_ms_max']} |",
        "",
        "## By kind",
        "",
    ]
    for kind, bucket in sorted(s["by_kind"].items()):
        lines.append(
            f"- **{kind}**: n={bucket['n']}, status_accuracy={bucket['status_accuracy']:.4f}"
        )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {n}" for n in report["notes"])
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, prefix: str = "baseline") -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = REPORT_DIR / f"{prefix}_{stamp}.json"
    md_path = REPORT_DIR / f"{prefix}_{stamp}.md"
    latest_json = REPORT_DIR / f"{prefix}_latest.json"
    latest_md = REPORT_DIR / f"{prefix}_latest.md"

    payload = json.dumps(report, indent=2)
    json_path.write_text(payload, encoding="utf-8")
    latest_json.write_text(payload, encoding="utf-8")
    md = _report_markdown(report)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    return latest_json, latest_md


def write_comparison(dense: dict[str, Any], hybrid: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ds, hs = dense["summary"], hybrid["summary"]

    def delta(key: str) -> str:
        a, b = ds.get(key), hs.get(key)
        if a is None or b is None:
            return "n/a"
        return f"{b - a:+.4f}"

    def row(label: str, key: str) -> str:
        return f"| {label} | {ds[key]} | {hs[key]} | {delta(key)} |"

    lines = [
        "# Hybrid vs dense retrieval (measured)",
        "",
        f"- Dense mode: `{dense['mode']}` @ `{dense['generated_at']}`",
        f"- Hybrid mode: `{hybrid['mode']}` @ `{hybrid['generated_at']}`",
        f"- Cases: {ds['n_cases']}",
        "",
        "| Metric | Dense | Hybrid | Delta |",
        "|--------|------:|-------:|------:|",
        row("Status accuracy", "status_accuracy"),
        row("Keyword accuracy", "keyword_accuracy"),
        row("Escalation accuracy", "escalation_accuracy"),
        row("Citation validity", "citation_validity"),
        row("Latency p50 (ms)", "latency_ms_p50"),
        "",
        "## Verdict",
        "",
        "_Keep hybrid only if status/keyword metrics improve without unacceptable "
        "latency. Numbers above are from this offline run — not fabricated._",
        "",
    ]
    path = REPORT_DIR / "hybrid_vs_dense_latest.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "hybrid_vs_dense_latest.json").write_text(
        json.dumps({"dense": dense["summary"], "hybrid": hybrid["summary"]}, indent=2),
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ResolveAI baseline evaluation")
    parser.add_argument("--live", action="store_true", help="Use Ollama + Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="Limit cases (debug)")
    parser.add_argument(
        "--retrieval-mode",
        choices=["dense", "hybrid"],
        default="dense",
        help="Retrieval mode for a single run",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run dense and hybrid side-by-side and write comparison report",
    )
    parser.add_argument(
        "--ensure-dataset",
        action="store_true",
        help="Build golden_v1.jsonl if missing",
    )
    args = parser.parse_args()
    if args.ensure_dataset or not GOLDEN.exists():
        from eval.datasets.build_golden import main as build_main

        build_main()

    if args.compare:
        dense = run_eval(live=args.live, limit=args.limit, retrieval_mode="dense")
        hybrid = run_eval(live=args.live, limit=args.limit, retrieval_mode="hybrid")
        write_report(dense, prefix="baseline_dense")
        write_report(hybrid, prefix="baseline_hybrid")
        path = write_comparison(dense, hybrid)
        print(path.read_text(encoding="utf-8"))
        print(f"Wrote {path}")
        return

    report = run_eval(
        live=args.live,
        limit=args.limit,
        retrieval_mode=args.retrieval_mode,
    )
    prefix = "baseline_hybrid" if args.retrieval_mode == "hybrid" else "baseline"
    json_path, md_path = write_report(report, prefix=prefix)
    print(md_path.read_text(encoding="utf-8"))
    print(f"Wrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
