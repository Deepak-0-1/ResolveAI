"""Liveness / readiness checks for Docker and load balancers."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from resolveai_common.settings import get_settings
from resolveai_db.session import check_postgres

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class DependencyStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(description="ok | degraded | error")
    app: str
    env: str
    dependencies: list[DependencyStatus] = Field(default_factory=list)


async def _check_http(name: str, url: str, timeout: float) -> DependencyStatus:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            if response.status_code < 500:
                return DependencyStatus(name=name, status="ok")
            return DependencyStatus(
                name=name,
                status="error",
                detail=f"HTTP {response.status_code}",
            )
    except Exception as exc:  # noqa: BLE001 — surface any connectivity failure
        logger.warning("health_check_failed", extra={"dependency": name})
        return DependencyStatus(name=name, status="unavailable", detail=str(exc))


def _check_database() -> DependencyStatus:
    ok, detail = check_postgres()
    if ok:
        return DependencyStatus(name="postgres", status="ok")
    return DependencyStatus(name="postgres", status="unavailable", detail=detail)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Liveness always returns 200 if the process is up.
    Dependency probes are best-effort so local API-only runs still work.
    """
    settings = get_settings()
    timeout = min(settings.http_timeout_seconds, 3.0)

    checks: list[DependencyStatus] = [
        _check_database(),
        await _check_http(
            "qdrant",
            f"{settings.qdrant_url}/readyz",
            timeout,
        ),
        await _check_http(
            "ollama",
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout,
        ),
    ]

    probed = [c.status for c in checks]
    overall = "degraded" if any(s in {"error", "unavailable"} for s in probed) else "ok"

    body: dict[str, Any] = {
        "status": overall,
        "app": settings.app_name,
        "env": settings.app_env,
        "dependencies": checks,
    }
    return HealthResponse(**body)


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Simple process liveness for orchestrators."""
    return {"status": "ready"}
