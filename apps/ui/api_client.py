"""Thin HTTP client for the ResolveAI FastAPI backend."""

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
