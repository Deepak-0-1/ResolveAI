"""M10 hardening: redaction, retries, production guards, middleware."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from resolveai_api.main import create_app
from resolveai_common.redact import redact
from resolveai_common.retry import with_retries
from resolveai_common.settings import Settings, get_settings
from resolveai_db.session import get_db


def test_redact_masks_bearer_and_secrets() -> None:
    text = "Authorization: Bearer abc.def.ghi password=super-secret token: xyz"
    cleaned = redact(text)
    assert "abc.def.ghi" not in cleaned
    assert "super-secret" not in cleaned
    assert "xyz" not in cleaned
    assert "[REDACTED]" in cleaned


def test_with_retries_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("temporary")
        return "ok"

    assert with_retries(flaky, retries=2, backoff_seconds=0.01, retry_on=(ConnectionError,)) == "ok"
    assert calls["n"] == 3


def test_with_retries_exhausted() -> None:
    def always_fail() -> None:
        raise TimeoutError("down")

    with pytest.raises(TimeoutError):
        with_retries(always_fail, retries=1, backoff_seconds=0.01, retry_on=(TimeoutError,))


def test_production_rejects_weak_secrets() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret="change-me-to-a-long-random-string",
        service_api_key="dev-service-api-key-change-me",
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.assert_safe_for_production()


def test_development_allows_defaults() -> None:
    Settings(app_env="development").assert_safe_for_production()


def test_security_headers_and_request_id() -> None:
    client = TestClient(create_app())
    response = client.get("/ready", headers={"X-Request-ID": "test-req-1"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-req-1"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


def test_rate_limit_returns_429(monkeypatch, db_engine) -> None:
    """Rate limit must not require live Postgres (CI has none)."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _override_get_db():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    try:
        app = create_app()
        app.dependency_overrides[get_db] = _override_get_db
        with TestClient(app) as client:
            # /ready,/health,/docs are excluded; /auth/login is rate-limited.
            statuses = [
                client.post(
                    "/auth/login",
                    json={"email": "nobody@example.com", "password": "x"},
                ).status_code
                for _ in range(5)
            ]
        assert 429 in statuses
    finally:
        get_settings.cache_clear()


def test_unhandled_error_hides_internal_detail() -> None:
    app = create_app()

    @app.get("/_boom")
    def boom() -> None:
        raise RuntimeError("password=should-not-leak")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert "should-not-leak" not in str(body)
    assert "password" not in str(body).lower() or body["detail"] == "Internal server error"
