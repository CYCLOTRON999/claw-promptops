"""Adapter subsystem factory and registry for CLAW PromptOps."""

from typing import Dict, List, Optional
from app.adapters.base import BaseModelAdapter, GenerationRequest, GenerationResponse, ModelInfo, StreamChunk
from app.adapters.mock import MockAdapter
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compatible import OpenAICompatibleAdapter
from app.config import settings

__all__ = [
    "BaseModelAdapter",
    "GenerationRequest",
    "GenerationResponse",
    "ModelInfo",
    "StreamChunk",
    "MockAdapter",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
    "get_adapter",
    "list_available_models"
]


def get_adapter(model_name: Optional[str] = None) -> BaseModelAdapter:
    """Factory resolving a model name to its corresponding concrete ModelAdapter instance."""
    name = (model_name or settings.default_model).strip()

    if name.startswith("mock") or name in ("deterministic-mock", "mock-fallback", "test-mock"):
        return MockAdapter(model_name=name)

    if name.startswith("ollama") or name in ("llama3", "llama3.1", "mistral", "phi3"):
        # Strip prefix if needed
        clean_model = name.replace("ollama-", "")
        return OllamaAdapter(model_name=clean_model, config={"base_url": settings.ollama_base_url})

    if name.startswith("gpt-") or name.startswith("openai") or "claude" in name or "groq" in name:
        return OpenAICompatibleAdapter(
            model_name=name,
            config={
                "base_url": settings.openai_base_url,
                "api_key": settings.openai_api_key
            }
        )

    # Safe default: return MockAdapter for unknown/test models
    return MockAdapter(model_name=name)


def list_available_models() -> List[ModelInfo]:
    """Return all pre-registered models and their capability metadata."""
    models = [
        MockAdapter("mock-deterministic").get_model_info(),
        MockAdapter("mock-fallback").get_model_info(),
        OllamaAdapter("llama3").get_model_info(),
        OllamaAdapter("mistral").get_model_info(),
        OpenAICompatibleAdapter("gpt-4o-mini").get_model_info(),
        OpenAICompatibleAdapter("gpt-4o").get_model_info(),
    ]
    return models
