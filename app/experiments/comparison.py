"""Comparison logic and side-by-side metric calculations for PromptOps experiments."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class VariantMetrics(BaseModel):
    """Aggregated metrics for a single experimental variant."""
    name: str
    prompt_version: str
    model: str
    total_runs: int
    schema_validity_pct: float
    instruction_following_pct: float
    avg_latency_ms: float
    avg_tokens: float
    total_cost_usd: float
    repair_rate_pct: float
    retry_rate_pct: float
    failure_rate_pct: float


class ExperimentComparisonReport(BaseModel):
    """Side-by-side comparison between two prompt versions or model configurations."""
    experiment_id: str
    name: str
    variant_a: VariantMetrics
    variant_b: VariantMetrics
    deltas: Dict[str, float] = Field(
        description="Measured difference (Variant B - Variant A) for key operational metrics"
    )


class ExperimentComparator:
    """Computes measured deltas and side-by-side performance metrics."""

    @staticmethod
    def compare(
        experiment_id: str,
        name: str,
        metrics_a: Dict[str, Any],
        metrics_b: Dict[str, Any]
    ) -> ExperimentComparisonReport:
        var_a = VariantMetrics(**metrics_a)
        var_b = VariantMetrics(**metrics_b)

        deltas = {
            "validity_delta_pct": round(var_b.schema_validity_pct - var_a.schema_validity_pct, 2),
            "instruction_score_delta_pct": round(var_b.instruction_following_pct - var_a.instruction_following_pct, 2),
            "latency_delta_ms": round(var_b.avg_latency_ms - var_a.avg_latency_ms, 2),
            "tokens_delta": round(var_b.avg_tokens - var_a.avg_tokens, 1),
            "cost_delta_usd": round(var_b.total_cost_usd - var_a.total_cost_usd, 6),
            "repair_rate_delta_pct": round(var_b.repair_rate_pct - var_a.repair_rate_pct, 2),
            "failure_rate_delta_pct": round(var_b.failure_rate_pct - var_a.failure_rate_pct, 2),
        }

        return ExperimentComparisonReport(
            experiment_id=experiment_id,
            name=name,
            variant_a=var_a,
            variant_b=var_b,
            deltas=deltas
        )
