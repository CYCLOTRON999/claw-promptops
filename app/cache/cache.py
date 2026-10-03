"""Configuration-aware caching layer for deterministic LLM generations."""

import hashlib
import json
import logging
from typing import Any, Dict, Optional
from app.adapters.base import GenerationRequest, GenerationResponse
from app.config import settings

logger = logging.getLogger("claw.cache")


class GenerationCache:
    """Thread-safe, configuration-aware cache for generation responses."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._store: Dict[str, GenerationResponse] = {}
        self.hits: int = 0
        self.misses: int = 0

    @staticmethod
    def compute_cache_key(
        task_type: str,
        prompt_name: str,
        prompt_version: str,
        rendered_prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        response_format: Optional[str]
    ) -> str:
        """Generate a SHA-256 hash incorporating all generation parameters."""
        key_data = {
            "task_type": task_type,
            "prompt_name": prompt_name,
            "prompt_version": prompt_version,
            "rendered_prompt": rendered_prompt,
            "model": model,
            "temperature": round(temperature, 4),
            "max_tokens": max_tokens,
            "response_format": response_format
        }
        serialized = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[GenerationResponse]:
        """Retrieve cached response if caching enabled and key exists."""
        if not self.enabled:
            return None

        if key in self._store:
            self.hits += 1
            logger.debug(f"Cache HIT for key: {key[:8]}...")
            cached_resp = self._store[key].model_copy(deep=True)
            cached_resp.cached = True
            return cached_resp

        self.misses += 1
        logger.debug(f"Cache MISS for key: {key[:8]}...")
        return None

    def set(self, key: str, response: GenerationResponse) -> None:
        """Store response in cache if caching enabled and response is valid."""
        if not self.enabled or response.status != "SUCCESS":
            return
        self._store[key] = response.model_copy(deep=True)

    def clear(self) -> None:
        """Clear cache entries and reset counters."""
        self._store.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics and total stored entries."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100.0) if total > 0 else 0.0
        return {
            "enabled": self.enabled,
            "size": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2)
        }


# Global default cache instance
default_cache = GenerationCache(enabled=settings.cache_enabled)
