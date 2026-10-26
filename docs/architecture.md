# ResolveAI Architecture

## Problem

Support teams spend time on repetitive, document-answerable questions while risky or novel cases need humans. Generic chatbots hallucinate. ResolveAI answers from a knowledge base with citations and escalates when it should not guess.

## Stack (approved)

| Layer | Choice | Why |
|-------|--------|-----|
| API | FastAPI | Typed HTTP, OpenAPI, middleware |
| UI | Streamlit | Fast dual-role demo (customer / admin) |
| Agent | LangGraph | Explicit classify → retrieve → act graph |
| LLM | Ollama `qwen2.5:3b` | Small, local, interview-demo friendly |
| Embeddings | Ollama `nomic-embed-text` | Local RAG embeddings |
| Relational DB | PostgreSQL | Tickets, users, audit, feedback |
| Vectors | Qdrant | Filtered semantic search |
| Auth | JWT + roles | Customer vs admin RBAC |
| Eval | Pytest + offline golden set | Measured quality, not vibes |

## Runtime flow

```text
User → Streamlit → FastAPI (JWT, rate limit, request ID, security headers)
                 → LangGraph
                      classify → tools | retrieve_answer (hybrid RAG) | escalate
                 → PostgreSQL + audit log
                 → Qdrant (+ BM25 fuse) / Ollama (embed + chat, with retries)
```

## Auth model

- Public `POST /auth/register` always creates `customer` (cannot self-elevate to admin).
- Admins come from seed or controlled provisioning.
- `Authorization: Bearer <JWT>` for users; `X-API-Key` reserved for eval/CI machines.
- Customers see only their tickets; admins see all.

## Knowledge base

```text
Upload (admin) → parse (PDF/DOCX/TXT/FAQ) → chunk → Ollama embed → Qdrant
                                                      ↘ Postgres knowledge_documents
```

Search (`POST /kb/search`) embeds the query and returns top chunks with scores and metadata.

## Grounded chat + agent

```text
POST /chat
  → LangGraph classify → route_intent
       ├─ tools: get_ticket | get_ticket_status | create_draft_response
       └─ retrieve_answer:
            sensitive keyword gate
            → hybrid retrieve (dense + BM25 RRF) or dense-only
            → escalate if empty / below MIN_RETRIEVAL_SCORE
            → Ollama answer constrained to numbered sources
            → keep only citations whose [n] maps to a real hit
            → audit log (+ optional ticket message / escalate status)
```

## UI roles

- **Customer:** chat, own tickets, feedback  
- **Admin:** same + KB upload/search + escalations queue + draft tool  

Streamlit talks only to FastAPI (JWT). No secrets beyond the access token in session state.

## Evaluation

- Dataset: `eval/datasets/golden_v1.jsonl` (120 cases)
- Runner: `python -m eval.runners.baseline` (`--compare`, `--live`)
- Reports: measured only under `eval/reports/`
- Offline harness uses HashEmbedder + FakeLLM — honest baselines, not live-model claims

## Hybrid retrieval

```text
query → dense top-N  ┐
                     ├─ Reciprocal Rank Fusion → top-k
query → BM25 top-N   ┘
```

Default `RETRIEVAL_MODE=hybrid`. Offline compare: **+0.13 keyword accuracy** vs dense with flat status/latency — hybrid kept. Rerank (M9) deferred unless a live eval shows lift.

## Hardening (M10)

| Control | Behavior |
|---------|----------|
| Rate limit | In-memory sliding window per client IP (`RATE_LIMIT_PER_MINUTE`) |
| Retries | Exponential backoff on Ollama embed/chat (`HTTP_MAX_RETRIES`) |
| Request ID | `X-Request-ID` echoed; generated if missing |
| Security headers | `nosniff`, `DENY` frame, `no-referrer`, `no-store` |
| Redaction | Strip bearer/password/token patterns before error logs |
| Production guard | Fail startup on weak JWT/API key/DB password when `APP_ENV=production` |
| Errors | Generic 500 body; no stack traces or secrets to clients |

## Deploy / CI (M11–M12)

See [deploy.md](deploy.md). Compose runs Postgres, Qdrant, Ollama, API (migrate-on-start), UI. CI lints, tests, validates Compose, builds images.

## Milestone map

| Milestone | Status |
|-----------|--------|
| M0–M8 foundation through hybrid | Done |
| M9 rerank | Skipped (no measured lift yet) |
| M10 hardening | Done |
| M11 Docker/CI | Done |
| M12 docs + limitations | Done |
