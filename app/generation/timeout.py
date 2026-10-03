"""Timeout enforcement subsystem for model generation calls."""

import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger("claw.timeout")


class ModelTimeoutError(asyncio.TimeoutError):
    """Raised when an external model request exceeds its configured execution window."""
    def __init__(self, message: str, timeout_seconds: float, model: str):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.model = model


async def execute_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout_seconds: float,
    model: str = "unknown"
) -> Any:
    """Execute coroutine with strict timeout enforcement."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        msg = f"Model execution '{model}' timed out after {timeout_seconds:.1f} seconds."
        logger.error(msg)
        raise ModelTimeoutError(msg, timeout_seconds=timeout_seconds, model=model) from exc
