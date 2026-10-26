"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from resolveai_api.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from resolveai_api.routers import auth, chat, feedback, health, kb, tickets
from resolveai_common.logging import configure_logging
from resolveai_common.redact import redact
from resolveai_common.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.assert_safe_for_production()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI customer support agent API (grounded RAG + escalation)",
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_exception",
            extra={
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "error": redact(str(exc)),
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
                "error_type": type(exc).__name__,
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tickets.router)
    app.include_router(kb.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    return app


app = create_app()
