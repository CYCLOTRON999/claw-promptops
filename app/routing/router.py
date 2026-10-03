"""Deterministic, explainable model router based on task classification and operational constraints."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.config import settings


class RoutingCriteria(BaseModel):
    """Inputs driving the deterministic model routing decision."""
    task_type: str = Field(default="event_brief", description="Task category (e.g. event_brief, content_pack, reasoning)")
    quality_priority: str = Field(default="standard", description="'low', 'standard', or 'high'")
    latency_priority: str = Field(default="balanced", description="'ultra_fast', 'balanced', or 'thorough'")
    max_cost_per_query: Optional[float] = Field(default=None, description="Maximum acceptable USD cost per query")
    require_offline: bool = Field(default=False, description="Strict offline constraint requiring local/mock compute")
    preferred_model: Optional[str] = Field(default=None, description="Explicit user model override if specified")


class RoutingDecision(BaseModel):
    """Auditable routing outcome explaining model selection and fallback chain."""
    selected_model: str
    routing_reason: str
    fallback_models: List[str]


class ModelRouter:
    """Deterministic routing engine explaining why a particular model was chosen."""

    @classmethod
    def route(cls, criteria: RoutingCriteria) -> RoutingDecision:
        # 1. Direct user preference override
        if criteria.preferred_model and criteria.preferred_model not in ("auto", "router", ""):
            return RoutingDecision(
                selected_model=criteria.preferred_model,
                routing_reason=f"Explicit user preference override: '{criteria.preferred_model}'",
                fallback_models=["mock-fallback"]
            )

        # 2. Strict offline / zero-dependency requirement
        if criteria.require_offline or criteria.max_cost_per_query == 0.0:
            return RoutingDecision(
                selected_model="mock-deterministic",
                routing_reason="Zero-cost or strict offline constraint enforced; routed to deterministic mock",
                fallback_models=["mock-fallback"]
            )

        # 3. High quality reasoning tasks
        if criteria.quality_priority == "high" or criteria.task_type in ("complex_reasoning", "multi_step"):
            # If OpenAI key configured, route to gpt-4o, else local llama3
            if settings.openai_api_key:
                return RoutingDecision(
                    selected_model="gpt-4o",
                    routing_reason="High quality priority + complex reasoning requirements; routed to frontier cloud model",
                    fallback_models=["gpt-4o-mini", "mock-fallback"]
                )
            return RoutingDecision(
                selected_model="llama3",
                routing_reason="High quality priority without external API key; routed to local llama3",
                fallback_models=["mock-fallback"]
            )

        # 4. Ultra-fast / low-latency extraction
        if criteria.latency_priority == "ultra_fast":
            return RoutingDecision(
                selected_model="llama3",
                routing_reason="Ultra-fast latency requirement for simple extraction; routed to local Ollama",
                fallback_models=["mock-fallback"]
            )

        # 5. Default balanced extraction
        return RoutingDecision(
            selected_model=settings.default_model,
            routing_reason=f"Standard '{criteria.task_type}' task under balanced latency and cost profile",
            fallback_models=["mock-fallback"]
        )
