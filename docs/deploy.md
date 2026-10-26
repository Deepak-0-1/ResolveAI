# Deploy & Run ResolveAI

Supported demo path: **Docker Compose on your machine** (or a small VPS with Docker).  
This is not a managed SaaS runbook — production notes are a hardening checklist.

Related: [architecture](architecture.md) · [API](api.md) · [README](../README.md)

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| Docker Desktop / Engine + Compose v2 | Required for the full stack |
| ~4 GB free RAM | Ollama + `qwen2.5:3b` + `nomic-embed-text` |
| Disk | Images + models (~3 GB+ first pull) |
| Ports free | `5432`, `6333`, `11434`, `8000`, `8501` |

---

## End-to-end (Compose) — recommended

### 1. Configure env

```bash
cp .env.example .env
```

Local defaults work for demos. For anything shared/public, replace `JWT_SECRET`, `SERVICE_API_KEY`, and DB password.

Key variables (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `APP_ENV` | `development` or `production` (strict secret checks) |
| `DATABASE_URL` / `POSTGRES_*` | Postgres |
| `QDRANT_HOST` / `QDRANT_PORT` | Vectors |
| `OLLAMA_BASE_URL` / models | LLM + embeddings |
| `RETRIEVAL_MODE` | `hybrid` (default) or `dense` |
| `MIN_RETRIEVAL_SCORE` | Escalate below this dense/hybrid score |
| `RATE_LIMIT_PER_MINUTE` | API sliding-window limit |
| `HTTP_MAX_RETRIES` | Ollama embed/chat retries |

### 2. Start all services

From the repo root:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

| Service | Role |
|---------|------|
| `postgres` | Relational data |
| `qdrant` | Vector index |
| `ollama` | Local LLM + embeddings |
| `api` | FastAPI; runs Alembic `upgrade head` on start (`apps/api/entrypoint.sh`) |
| `ui` | Streamlit |

### 3. Pull models (first time)

```bash
docker compose -f docker/docker-compose.yml exec ollama ollama pull qwen2.5:3b
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text
docker compose -f docker/docker-compose.yml exec ollama ollama list
```

Expect both models listed before chatting.

### 4. Seed users + knowledge base

```bash
docker compose -f docker/docker-compose.yml exec api resolveai-seed
docker compose -f docker/docker-compose.yml exec api resolveai-seed-kb
```

- Seed creates demo accounts.
- KB seed indexes `data/kb/` into Postgres + Qdrant (idempotent skip if already indexed).

### 5. Verify

```bash
curl http://localhost:8000/ready
curl http://localhost:8000/health
```

| Surface | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| API OpenAPI | http://localhost:8000/docs |
| Ready | http://localhost:8000/ready |

### 6. Demo logins

| Role | Email | Password |
|------|-------|----------|
| Customer | `customer@resolveai.local` | `customer123!` |
| Admin | `admin@resolveai.local` | `admin123!` |

**Demo script ideas**

1. Customer chat: “How do I reset my password?” → citations  
2. Sensitive: “I need to delete my workspace” → escalate  
3. Admin: KB list / upload; escalations queue  
4. Ticket create + ask status in chat (tool path)

### 7. Logs & rebuild

```bash
docker compose -f docker/docker-compose.yml logs -f api
docker compose -f docker/docker-compose.yml up -d --build api
```

After code changes under `packages/` or `apps/api`, rebuild the API image so the container picks them up.

### 8. Stop

```bash
docker compose -f docker/docker-compose.yml down
# keep volumes:
# docker compose -f docker/docker-compose.yml down -v   # wipes DB/vectors/models data
```

Volumes: `postgres_data`, `qdrant_data`, `ollama_data`.

---

## Host Python + Compose deps only

Use when iterating on API/UI without rebuilding the API image every time.

```powershell
pip install -e ".[dev]"
$env:PYTHONPATH = "packages/common/src;packages/db/src;packages/rag/src;packages/agent/src;apps/api/src"

docker compose -f docker/docker-compose.yml up -d postgres qdrant ollama
# pull ollama models as above (exec into ollama service)

alembic -c packages/db/alembic.ini upgrade head
resolveai-seed
resolveai-seed-kb
uvicorn resolveai_api.main:app --reload --host 127.0.0.1 --port 8000
```

UI:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
streamlit run apps/ui/app.py
```

Point `.env` at `localhost` hosts for Postgres/Qdrant/Ollama (defaults in `.env.example`).

---

## Tests & eval

```powershell
pytest tests -q

$env:PYTHONPATH = ".;packages/common/src;packages/db/src;packages/rag/src;packages/agent/src;apps/api/src"
python -m eval.runners.baseline --compare   # offline HashEmbedder + FakeLLM
# python -m eval.runners.baseline --live    # needs running Ollama + seeded KB
```

---

## Production checklist

Set `APP_ENV=production`. Startup calls `Settings.assert_safe_for_production()` and **refuses** weak defaults for:

- `JWT_SECRET` — unique, length ≥ 32  
- `SERVICE_API_KEY` — not the example value  
- `POSTGRES_PASSWORD` — not `resolveai` / `postgres` / `password`

Also:

1. Terminate TLS at a reverse proxy; do not expose Postgres, Qdrant, or Ollama publicly.  
2. Tune `RATE_LIMIT_PER_MINUTE` — limiter is **in-memory per process**, not shared across replicas.  
3. Persist Compose volumes or use managed Postgres/Qdrant.  
4. Never commit `.env` (`.gitignore` already excludes it).  
5. Prefer pinning image tags; rebuild API after dependency/API changes.  
6. GitHub alone does **not** host the demo — you need a machine with Docker.

---

## CI

Workflow: `.github/workflows/ci.yml`

- Ruff lint + format check  
- `pytest tests`  
- `docker compose … config`  
- Build API + UI images on PR/push  

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| UI “Internal server error” on chat | Check `docker compose … logs api`; ensure models pulled; rebuild API after code fixes |
| `QdrantClient` / search errors | API uses `query_points` (client 1.20+); rebuild API image |
| KB seed logging `filename` KeyError | Fixed — use current `seed_kb` / rebuild API |
| Chat slow / timeout | First Ollama call loads the model; wait or increase client timeout |
| `/health` degraded | Postgres/Qdrant/Ollama not ready yet — wait and retry |
| Login email validation | Use `*.local` seed accounts; API allows them |
| Port in use | Stop other Postgres/Ollama or change Compose port mappings |

---

## Compose topology

```text
UI :8501 ──▶ API :8000 ──▶ Postgres :5432
                 │
                 ├──▶ Qdrant :6333
                 └──▶ Ollama :11434
```
