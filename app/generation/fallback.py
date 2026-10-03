"""Fallback execution subsystem when primary model backend is exhausted or fails."""

import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from app.adapters.base import BaseModelAdapter, GenerationRequest, GenerationResponse
from app.adapters import get_adapter

logger = logging.getLogger("claw.fallback")


class FallbackHandler:
    """Manages secondary and disaster-recovery model execution chains."""

    DEFAULT_FALLBACK_CHAINS: Dict[str, List[str]] = {
        "gpt-4o": ["gpt-4o-mini", "mock-fallback"],
        "gpt-4o-mini": ["mock-fallback"],
        "llama3": ["mistral", "mock-fallback"],
        "mistral": ["llama3", "mock-fallback"],
        "mock-deterministic": ["mock-fallback"]
    }

    @classmethod
    def get_fallback_models(cls, primary_model: str) -> List[str]:
        """Determine ordered list of fallback models for a given primary model."""
        return cls.DEFAULT_FALLBACK_CHAINS.get(primary_model, ["mock-fallback"])

    @classmethod
    async def execute_fallback(
        cls,
        request: GenerationRequest,
        primary_error: str,
        fallback_models: Optional[List[str]] = None
    ) -> GenerationResponse:
        """Attempt generation through sequentially ordered fallback models."""
        candidates = fallback_models or cls.get_fallback_models(request.model)
        last_err = primary_error

        for fallback_model_name in candidates:
            logger.warning(f"Primary model '{request.model}' failed ({primary_error}). Activating fallback: '{fallback_model_name}'")
            fallback_adapter = get_adapter(fallback_model_name)

            fallback_request = request.model_copy(deep=True)
            fallback_request.model = fallback_model_name
            fallback_request.metadata["fallback_activated"] = True
            fallback_request.metadata["original_model"] = request.model

            try:
                response = await fallback_adapter.generate(fallback_request)
                response.fallback_used = True
                response.fallback_model = fallback_model_name
                logger.info(f"Fallback generation through '{fallback_model_name}' succeeded.")
                return response
            except Exception as exc:
                last_err = str(exc)
                logger.error(f"Fallback model '{fallback_model_name}' also failed: {last_err}")

        # All fallbacks failed
        return GenerationResponse(
            text="",
            model=request.model,
            provider="fallback",
            status="FAILED",
            error=f"Primary model and all fallbacks ({', '.join(candidates)}) failed. Last error: {last_err}",
            fallback_used=True,
            fallback_model=candidates[-1] if candidates else None
        )
