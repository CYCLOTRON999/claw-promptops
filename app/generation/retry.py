"""Bounded exponential backoff retry subsystem for transient network and provider failures."""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple, Type
import httpx
from app.adapters.mock import MockAdapterError

logger = logging.getLogger("claw.retry")

TRANSIENT_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    asyncio.TimeoutError,
    TimeoutError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.NetworkError,
    MockAdapterError
)


def is_transient_error(exc: Exception) -> bool:
    """Determine whether an error is transient (retryable) or permanent."""
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        # 429 (Rate Limit), 502 (Bad Gateway), 503 (Service Unavailable), 504 (Gateway Timeout)
        return exc.response.status_code in (429, 502, 503, 504)

    err_msg = str(exc).lower()
    if any(k in err_msg for k in ["timeout", "connection reset", "temporarily unavailable", "503", "429"]):
        return True

    return False


class RetryEngine:
    """Executes asynchronous callables with bounded exponential backoff retries."""

    @classmethod
    async def execute_with_retry(
        cls,
        operation: Callable[[], Coroutine[Any, Any, Any]],
        max_retries: int = 2,
        initial_delay: float = 0.05,
        backoff_factor: float = 2.0,
        max_delay: float = 2.0,
        task_label: str = "model_generation"
    ) -> Tuple[Any, int, Optional[str]]:
        """Run operation with exponential backoff on transient errors.

        Returns (result, retry_count, last_error_message).
        Raises last exception if permanent error or retries exhausted.
        """
        attempt = 0
        current_delay = initial_delay
        last_error: Optional[str] = None

        while True:
            try:
                result = await operation()
                return result, attempt, None
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)}"
                if not is_transient_error(exc):
                    logger.warning(f"[{task_label}] Permanent error encountered, skipping retry: {last_error}")
                    raise exc

                if attempt >= max_retries:
                    logger.error(f"[{task_label}] Exhausted all {max_retries} retries. Last error: {last_error}")
                    raise exc

                attempt += 1
                logger.warning(
                    f"[{task_label}] Transient error on attempt {attempt}/{max_retries}: {last_error}. "
                    f"Backing off for {current_delay:.2f}s..."
                )
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * backoff_factor, max_delay)
