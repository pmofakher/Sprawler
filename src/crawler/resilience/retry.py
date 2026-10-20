"""Retry strategies with exponential backoff and jitter for transient errors."""

import asyncio
import random
from typing import Any, Callable, Coroutine, TypeVar

import httpx

from crawler.core.exceptions import (
    CrawlerException,
    InvalidUrlSchemeException,
    RobotsDisallowedException,
    SSRFSecurityException,
)
from crawler.core.logging import logger

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    """Classifies whether an exception is considered transient and eligible for retry."""
    # Permanent application/security rejections
    if isinstance(exc, (SSRFSecurityException, InvalidUrlSchemeException, RobotsDisallowedException)):
        return False

    # HTTP Status checking
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        # Client errors are permanent
        if 400 <= code < 500:
            return False
        # Server errors (502, 503, 504) are transient
        if code in (502, 503, 504):
            return True
        return False

    # Network, connect, and timeout errors are transient
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, TimeoutError)):
        return True

    return False


async def execute_with_retry(
    coro_func: Callable[[], Coroutine[Any, Any, T]],
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    domain: str = "",
) -> T:
    """Executes an async callable with exponential backoff and randomized jitter."""
    attempt = 1
    while True:
        try:
            return await coro_func()
        except Exception as exc:
            if attempt >= max_attempts or not is_transient_error(exc):
                raise exc

            # Calculate backoff with jitter
            base_delay = min_wait * (2 ** (attempt - 1))
            jitter = random.uniform(0.5, 1.5)
            delay = min(max_wait, base_delay * jitter)

            logger.warning(
                f"Transient error on attempt {attempt}/{max_attempts} for {domain}: {exc}. Retrying in {delay:.2f}s...",
                extra={"domain": domain},
            )
            await asyncio.sleep(delay)
            attempt += 1
