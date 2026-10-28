"""Thin HTTP client and API helper functions for the ResolveAI FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            url,
            headers=headers,
            json=json,
            files=files,
            params=params,
        )
    if response.status_code >= 400:
        detail = response.text
        try:
            payload = response.json()
            detail = str(payload.get("detail", payload))
        except Exception:  # noqa: BLE001
            pass
        raise ApiError(detail, status_code=response.status_code)
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


# --- Typed Convenience Helpers ---

def login_user(email: str, password: str) -> dict[str, Any]:
    payload = request("POST", "/auth/login", json={"email": email, "password": password})
    token = payload["access_token"]
    user_info = request("GET", "/auth/me", token=token)
    return {"token": token, "user": user_info}


def get_analytics_overview(token: str) -> dict[str, Any]:
    return request("GET", "/analytics/overview", token=token)


def list_tickets(token: str, status: str | None = None) -> list[dict[str, Any]]:
    params = {"status": status} if status and status.lower() != "all" else None
    return request("GET", "/tickets", token=token, params=params) or []


def get_ticket_detail(ticket_id: str, token: str) -> dict[str, Any]:
    return request("GET", f"/tickets/{ticket_id}", token=token)


def create_ticket(
    token: str,
    subject: str,
    body: str,
    category: str | None = None,
    priority: str = "medium",
    urgency: str = "medium",
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "subject": subject,
        "body": body,
        "priority": priority,
        "urgency": urgency,
    }
    if category:
        data["category"] = category
    return request("POST", "/tickets", token=token, json=data)


def update_ticket(
    ticket_id: str,
    token: str,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    urgency: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if status is not None:
        payload["status"] = status
    if category is not None:
        payload["category"] = category
    if priority is not None:
        payload["priority"] = priority
    if urgency is not None:
        payload["urgency"] = urgency
    return request("PATCH", f"/tickets/{ticket_id}", token=token, json=payload)


def add_ticket_message(
    ticket_id: str,
    content: str,
    token: str,
    role: str = "agent",
) -> dict[str, Any]:
    return request(
        "POST",
        f"/tickets/{ticket_id}/messages",
        token=token,
        json={"content": content, "role": role},
    )


def save_ticket_draft(ticket_id: str, draft_body: str, token: str) -> dict[str, Any]:
    return request(
        "POST",
        f"/tickets/{ticket_id}/draft",
        token=token,
        json={"body": draft_body},
    )


def send_chat_message(
    message: str,
    token: str,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message}
    if ticket_id:
        payload["ticket_id"] = ticket_id
    return request("POST", "/chat", token=token, json=payload, timeout=180.0)


def send_feedback(
    rating: int,
    token: str,
    comment: str | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"rating": rating}
    if comment:
        payload["comment"] = comment
    if ticket_id:
        payload["ticket_id"] = ticket_id
    return request("POST", "/feedback", token=token, json=payload)


def list_kb_documents(token: str) -> list[dict[str, Any]]:
    return request("GET", "/kb/documents", token=token) or []


def upload_kb_document(
    filename: str,
    data: bytes,
    content_type: str,
    token: str,
) -> dict[str, Any]:
    return request(
        "POST",
        "/kb/documents",
        token=token,
        files={"file": (filename, data, content_type or "application/octet-stream")},
        timeout=300.0,
    )


def search_kb(query: str, token: str, limit: int = 5) -> dict[str, Any]:
    return request(
        "POST",
        "/kb/search",
        token=token,
        json={"query": query, "limit": limit},
    )


def get_system_health() -> dict[str, Any]:
    return request("GET", "/health")


def get_jira_status(token: str) -> dict[str, Any]:
    return request("GET", "/jira/status", token=token)


def get_jira_issue(issue_key: str, token: str) -> dict[str, Any]:
    return request("GET", f"/jira/issues/{issue_key}", token=token)


def investigate_jira_issue(
    issue_key: str,
    token: str,
    override_summary: str | None = None,
    override_description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"issue_key": issue_key}
    if override_summary:
        payload["override_summary"] = override_summary
    if override_description:
        payload["override_description"] = override_description
    return request("POST", "/jira/investigate", token=token, json=payload, timeout=180.0)


def publish_jira_comment(
    issue_key: str,
    comment: str,
    token: str,
) -> dict[str, Any]:
    return request(
        "POST",
        f"/jira/issues/{issue_key}/comment",
        token=token,
        json={"comment": comment},
    )


def get_jira_transitions(issue_key: str, token: str) -> list[dict[str, Any]]:
    return request("GET", f"/jira/issues/{issue_key}/transitions", token=token) or []


def execute_jira_transition(
    issue_key: str,
    transition_name: str,
    token: str,
) -> dict[str, Any]:
    return request(
        "POST",
        f"/jira/issues/{issue_key}/transitions",
        token=token,
        json={"transition": transition_name},
    )


