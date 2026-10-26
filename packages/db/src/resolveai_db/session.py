"""Engine and session factory. URL comes from settings (env)."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from resolveai_common.settings import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    # Fail fast when Postgres is down (health checks / local API-only runs).
    return {"connect_timeout": 3}


def get_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    global _engine, _session_factory
    if url is not None:
        return create_engine(url, echo=echo, future=True, connect_args=_connect_args(url))

    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            echo=echo,
            future=True,
            pool_pre_ping=True,
            connect_args=_connect_args(settings.database_url),
        )
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    global _session_factory
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


def reset_engine() -> None:
    """Clear cached engine (used in tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    session = (factory or get_session_factory())()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_postgres() -> tuple[bool, str | None]:
    """Return (ok, error_detail) for health probes."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
