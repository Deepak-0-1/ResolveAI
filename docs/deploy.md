# Deploy ResolveAI

Local Docker Compose is the supported demo path. Treat production notes as a hardening checklist, not a managed SaaS runbook.

## Prerequisites

- Docker Desktop (or Engine + Compose v2)
- ~4 GB RAM for Ollama + models (`qwen2.5:3b`, `nomic-embed-text`)
- Copy `.env.example` → `.env` and replace secrets before any non-local use

## Full stack

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml exec ollama ollama pull qwen2.5:3b
docker compose -f docker/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Ready probe | http://localhost:8000/ready |
| Streamlit UI | http://localhost:8501 |

API container runs Alembic `upgrade head` on start (`apps/api/entrypoint.sh`).

### Seed data (first boot)

With API dependencies up:

```bash
docker compose -f docker/docker-compose.yml exec api resolveai-seed
docker compose -f docker/docker-compose.yml exec api resolveai-seed-kb
```

Demo logins (from `.env.example`):

| Email | Password | Role |
|-------|----------|------|
| `customer@resolveai.local` | `customer123!` | customer |
| `admin@resolveai.local` | `admin123!` | admin |

## API-only (host Python)

```powershell
pip install -e ".[dev]"
$env:PYTHONPATH = "packages/common/src;packages/db/src;packages/rag/src;packages/agent/src;apps/api/src"
docker compose -f docker/docker-compose.yml up -d postgres qdrant ollama
alembic -c packages/db/alembic.ini upgrade head
resolveai-seed
resolveai-seed-kb
uvicorn resolveai_api.main:app --reload --host 127.0.0.1 --port 8000
```

UI in another shell:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
streamlit run apps/ui/app.py
```

## Production checklist

Set `APP_ENV=production`. Startup calls `Settings.assert_safe_for_production()` and **refuses** weak defaults for:

- `JWT_SECRET` (must be unique, length ≥ 32)
- `SERVICE_API_KEY`
- `POSTGRES_PASSWORD` (not `resolveai` / `postgres` / `password`)

Also:

1. Put TLS in front (reverse proxy); do not expose Postgres/Qdrant/Ollama publicly.
2. Raise or tune `RATE_LIMIT_PER_MINUTE` per replica (limiter is **in-memory**, not shared across replicas).
3. Persist volumes (`postgres_data`, `qdrant_data`, `ollama_data`).
4. Prefer managed Postgres/Qdrant if leaving the laptop.
5. Never commit `.env` — only `.env.example` with placeholders.

## Health

- `GET /ready` — process up (Compose healthcheck)
- `GET /health` — best-effort Postgres / Qdrant / Ollama probes (`ok` | `degraded`)

## CI

GitHub Actions (`.github/workflows/ci.yml`): Ruff lint + format check, pytest, Compose config validation, Docker image builds for API and UI.
