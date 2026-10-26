from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from resolveai_api.main import create_app
from resolveai_api.routers.health import DependencyStatus


def test_ready_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def _ok_http(name: str, url: str, timeout: float) -> DependencyStatus:
    return DependencyStatus(name=name, status="ok")


def test_health_lists_dependencies() -> None:
    with (
        patch("resolveai_api.routers.health.check_postgres", return_value=(True, None)),
        patch(
            "resolveai_api.routers.health._check_http",
            new=AsyncMock(side_effect=_ok_http),
        ),
    ):
        client = TestClient(create_app())
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "ResolveAI"
    assert body["status"] == "ok"
    names = {d["name"] for d in body["dependencies"]}
    assert {"qdrant", "ollama", "postgres"} <= names
