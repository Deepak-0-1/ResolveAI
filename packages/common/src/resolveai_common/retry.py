"""Small retry helper with exponential backoff (no extra dependency)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


def with_retries(
    fn: Callable[[], T],
    *,
    retries: int = 2,
    backoff_seconds: float = 0.4,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    operation: str = "operation",
) -> T:
    """
    Execute `fn` with retries. Does not retry on KeyboardInterrupt/SystemExit.
    Never logs secrets — callers must not put tokens into `operation`.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except retry_on as exc:
            attempt += 1
            if attempt > retries:
                logger.warning(
                    "retry_exhausted",
                    extra={
                        "operation": operation,
                        "attempts": attempt,
                        "error": type(exc).__name__,
                    },
                )
                raise
            sleep_for = backoff_seconds * (2 ** (attempt - 1))
            logger.info(
                "retrying",
                extra={
                    "operation": operation,
                    "attempt": attempt,
                    "sleep_seconds": sleep_for,
                    "error": type(exc).__name__,
                },
            )
            time.sleep(sleep_for)
