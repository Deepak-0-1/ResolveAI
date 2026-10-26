# ResolveAI API

Auth: `Authorization: Bearer <jwt>` from `POST /auth/login`. Interactive docs: `/docs`.

## Health

| Method | Path | Notes |
|--------|------|-------|
| GET | `/ready` | Process liveness (Compose healthcheck); not rate-limited |
| GET | `/health` | Best-effort dependency probes (Postgres, Qdrant, Ollama) |

## Auth

| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/register` | Always creates `customer` |
| POST | `/auth/login` | Returns JWT access token |
| GET | `/auth/me` | Current user |

## Tickets

| Method | Path | Notes |
|--------|------|-------|
| POST | `/tickets` | Create ticket + first message |
| GET | `/tickets` | List (own, or all if admin). Query `?status=escalated` |
| GET | `/tickets/{id}` | Detail + messages |
| GET | `/tickets/{id}/status` | **Tool** — status/priority/urgency |
| POST | `/tickets/{id}/draft` | **Tool** — store `[DRAFT]` reply, **never sends** |

RBAC: customers only access their tickets; admins access all.

## Chat / KB / feedback

| Method | Path | Notes |
|--------|------|-------|
| POST | `/chat` | LangGraph agent (classify → tools \| hybrid RAG) |
| POST | `/kb/documents` | Admin upload |
| GET | `/kb/documents` | Admin list |
| POST | `/kb/search` | Retrieval (mode from `RETRIEVAL_MODE`) |
| POST | `/feedback` | `rating` = `1` or `-1` |

## Cross-cutting (M10)

- **Rate limit:** `429` + `Retry-After` when over `RATE_LIMIT_PER_MINUTE` (excludes `/ready`, `/health`, `/docs`, OpenAPI).
- **Request ID:** send or receive `X-Request-ID`.
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`.
- **Errors:** unexpected failures return `{ "detail": "Internal server error", "request_id", "error_type" }` — no internal messages.
