# ResolveAI API Reference

Base URL (local): `http://localhost:8000`  
Interactive OpenAPI: [`/docs`](http://localhost:8000/docs) · ReDoc: `/redoc`

Auth header after login:

```http
Authorization: Bearer <access_token>
```

---

## Cross-cutting behavior

| Concern | Behavior |
|---------|----------|
| Rate limit | `429` + `Retry-After: 60` when over `RATE_LIMIT_PER_MINUTE` (default 60/min per client IP). Excludes `/ready`, `/health`, `/docs`, `/openapi.json`, `/redoc`. |
| Request ID | Send `X-Request-ID` or receive a generated one on every response. |
| Security headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` |
| Unexpected errors | `500` → `{ "detail": "Internal server error", "request_id": "...", "error_type": "..." }` — no stack traces or secrets |
| Emails | Demo domains like `*.local` are accepted (custom validator; standard `EmailStr` rejects them) |

---

## Health

### `GET /ready`

Process liveness (Compose healthcheck). Not rate-limited.

```json
{ "status": "ready" }
```

### `GET /health`

Best-effort probes of Postgres, Qdrant, Ollama. Always `200` if the process is up; `status` is `ok` or `degraded`.

```json
{
  "status": "ok",
  "app": "ResolveAI",
  "env": "development",
  "dependencies": [
    { "name": "postgres", "status": "ok" },
    { "name": "qdrant", "status": "ok" },
    { "name": "ollama", "status": "ok" }
  ]
}
```

---

## Auth

### `POST /auth/register`

Always creates a **customer**. Cannot self-elevate to admin.

```json
{
  "email": "newuser@example.com",
  "password": "password123!",
  "full_name": "New User"
}
```

→ `201` `UserOut`

### `POST /auth/login`

```json
{
  "email": "customer@resolveai.local",
  "password": "customer123!"
}
```

→

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### `GET /auth/me`

Requires JWT. → current `UserOut` (`id`, `email`, `full_name`, `role`, `is_active`, `created_at`).

---

## Tickets

RBAC: customers only their tickets; admins all.

### `POST /tickets`

Create ticket + first user message.

```json
{
  "subject": "Cannot reset password",
  "body": "Forgot password email never arrives.",
  "category": "account",
  "priority": "medium",
  "urgency": "medium"
}
```

→ `201` `TicketOut`

### `GET /tickets`

List. Query: `?status=escalated` (and other ticket statuses).

### `GET /tickets/{id}`

Detail + `messages[]`.

### `GET /tickets/{id}/status` *(agent tool surface)*

Returns status / priority / urgency for the agent or UI.

### `POST /tickets/{id}/draft` *(agent tool surface)*

Stores a `[DRAFT]` assistant message. **Never sends email.**

```json
{ "body": "Suggested reply text…" }
```

---

## Chat

### `POST /chat`

Runs the LangGraph support agent (classify → tools \| hybrid RAG \| escalate).

```json
{
  "message": "How do I reset my password?",
  "ticket_id": null
}
```

Optional `ticket_id`: appends user/assistant messages and may set status to `escalated`.

Example success:

```json
{
  "status": "answered",
  "answer": "… grounded text with [1] …",
  "citations": [
    {
      "index": 1,
      "chunk_id": "…",
      "document_id": "…",
      "title": "novadesk_account.faq",
      "filename": "novadesk_account.faq.txt",
      "snippet": "…",
      "score": 0.67
    }
  ],
  "escalation_reason": null,
  "retrieval_hit_count": 5,
  "top_score": 0.67,
  "ticket_id": null,
  "category": "account",
  "priority": "medium",
  "urgency": "medium",
  "tools_used": [],
  "tool_result": null,
  "trace": ["classify", "route_intent:retrieve", "retrieve_answer:answered"]
}
```

`status` values: `answered` | `escalated` (and tool-path answers).  
`trace` is the agent path for demos/debugging.

Timeouts: chat can take tens of seconds while Ollama runs; UI uses a long client timeout (~180s).

---

## Knowledge base (admin)

### `POST /kb/documents`

Multipart upload (`file`). Parses, chunks, embeds, upserts to Qdrant, records `knowledge_documents`.

### `GET /kb/documents`

List documents (`id`, `filename`, `title`, `status`, `chunk_count`, …).

### `POST /kb/search`

```json
{ "query": "password reset", "limit": 5 }
```

→ hits with `chunk_id`, `score`, `text`, document metadata. Retrieval mode follows `RETRIEVAL_MODE` (`hybrid` \| `dense`).

---

## Feedback

### `POST /feedback`

```json
{
  "rating": 1,
  "comment": "optional",
  "ticket_id": null
}
```

`rating`: `1` (helpful) or `-1` (not helpful).

---

## Curl smoke path

```bash
# login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"customer@resolveai.local","password":"customer123!"}' \
  | jq -r .access_token)

# chat
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"How do I reset my password?"}'
```

PowerShell equivalent uses `Invoke-RestMethod` with the same JSON bodies.

---

## Related

- [Architecture](architecture.md)
- [Deploy](deploy.md)
