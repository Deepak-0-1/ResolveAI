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

## Jira Integration & AI Investigation

Enterprise Jira Cloud integration layer with hybrid RAG, precedent searching, and safe human-in-the-loop workflows.

> **7. Remaining Incomplete Features or Known Gaps & Deliberate Safety Constraints:**
> - **Atlassian Webhooks**: Inbound Jira webhooks (automatic triggering on issue creation in Jira) are not implemented; investigation is currently initiated on-demand by authorized staff to prevent runaway LLM costs and ensure human oversight.
> - **Bi-directional Status Synchronization**: The application deliberately refrains from auto-transitioning Jira issue statuses (e.g. Open -> Resolved) to satisfy safety and least-privilege requirements; state transitions remain under staff discretion.

### `GET /jira/status`
Check connection health, base URL, and project key configuration. Requires Admin role.

### `GET /jira/issues/{issue_key}`
Fetch issue summary, ADF-parsed description, priority, status, and comments from Jira (or built-in sandbox for `DEMO-101`, `DEMO-102`). Requires Admin role.

### `POST /jira/investigate`
Execute LangGraph AI investigation on a Jira issue key:
```json
{
  "issue_key": "SUP-101",
  "override_summary": "Optional manual override",
  "override_description": "Optional manual override"
}
```
Returns structured report with citations, historical precedents, diagnostic steps, root cause hypothesis, recommended resolution, and draft Jira comment. Requires Admin role.

### `POST /jira/issues/{issue_key}/comment`
Explicitly authorized publish endpoint:
```json
{
  "comment": "Approved markdown or ADF text to publish to Jira"
}
```
Includes duplicate comment detection to prevent redundant postings. Requires Admin role.

### `GET /jira/issues/{issue_key}/transitions`
Retrieve available workflow transitions for an issue. Requires Admin role.

### `POST /jira/issues/{issue_key}/transitions`
Execute a chosen status transition under staff discretion:
```json
{
  "transition": "In Progress"
}
```
Requires Admin role.

### `POST /jira/webhook`
Inbound webhook receiver for Atlassian Jira Cloud events. Validates `X-Atlassian-Webhook-Secret` or `?secret=` query parameter and logs audit trail.

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

# jira investigation (admin token)
curl -s -X POST http://localhost:8000/jira/investigate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"issue_key":"DEMO-101"}'
```

PowerShell equivalent uses `Invoke-RestMethod` with the same JSON bodies.

---

## Related

- [Architecture](architecture.md)
- [Deploy](deploy.md)

