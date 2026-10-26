# ResolveAI

Production-oriented **AI customer support agent**: grounded RAG answers with citations, ticket tools, and human escalation when confidence is low or the request is sensitive.

## Status

**Milestones M0–M8 + M10–M12 complete.** M9 (rerank) skipped pending live-eval lift.

| Area | Status |
|------|--------|
| Auth, KB, LangGraph, tools, Streamlit | Done |
| Eval harness (120 cases) | Done |
| Hybrid retrieval (dense + BM25 RRF) | Done |
| Hardening (rate limit, retries, headers, redaction) | Done |
| Docker Compose + CI image builds | Done |
| Docs (architecture / API / deploy) | Done |
| Reranking | Skipped (M9) |

## Quick start (Compose)

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml exec ollama ollama pull qwen2.5:3b
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text
docker compose -f docker/docker-compose.yml exec api resolveai-seed
docker compose -f docker/docker-compose.yml exec api resolveai-seed-kb
```

- UI: http://localhost:8501  
- API: http://localhost:8000/docs  

| Email | Password |
|-------|----------|
| `customer@resolveai.local` | `customer123!` |
| `admin@resolveai.local` | `admin123!` |

More detail: [docs/deploy.md](docs/deploy.md) · [docs/architecture.md](docs/architecture.md) · [docs/api.md](docs/api.md)

## Offline eval (measured)

### Dense vs hybrid (`python -m eval.runners.baseline --compare`)

| Metric | Dense | Hybrid | Delta |
|--------|------:|-------:|------:|
| Status accuracy | 0.70 | 0.70 | 0.00 |
| Keyword accuracy | 0.27 | **0.40** | **+0.13** |
| Escalation accuracy | 0.85 | 0.85 | 0.00 |
| Citation validity | 1.00 | 1.00 | 0.00 |
| Latency p50 (ms) | 7.02 | 6.76 | -0.26 |

**Decision:** keep **`RETRIEVAL_MODE=hybrid`**. Report: `eval/reports/hybrid_vs_dense_latest.md`.

```powershell
$env:PYTHONPATH = ".;packages/common/src;packages/db/src;packages/rag/src;packages/agent/src;apps/api/src"
python -m eval.runners.baseline --compare
pytest tests -q
```

## Limitations (honest)

- **Local demo stack**, not multi-tenant SaaS: single-process rate limiter, default secrets in `.env.example` only for local use.
- Offline eval uses **HashEmbedder + FakeLLM** — keyword/status metrics are comparable across retrieval modes, not a claim about live `qwen2.5:3b` quality. Use `--live` when Ollama is up for real answers.
- Small chat model will miss nuance; escalation keywords + score floor are the safety net, not perfect policy.
- No cross-replica rate limiting, no WAF, no managed secrets — see production checklist in [docs/deploy.md](docs/deploy.md).
- Reranking not shipped; hybrid RRF was enough for the offline keyword lift measured here.
- PDF/DOCX parsers are optional-path imports; exotic encodings may need care.

## License

Proprietary / project demo — adjust as needed.
