"""Configurable cost calculation for model generation token usage."""

from typing import Dict, Optional
from app.config import settings


class CostCalculator:
    """Computes exact estimated USD cost based on token counts and model pricing."""

    @staticmethod
    def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Compute USD cost. Returns None if model pricing is not configured."""
        pricing = settings.get_pricing_for_model(model_name)
        if pricing is None:
            return None

        in_price_1k = pricing.get("input_price_per_1k", 0.0)
        out_price_1k = pricing.get("output_price_per_1k", 0.0)

        in_cost = (input_tokens / 1000.0) * in_price_1k
        out_cost = (output_tokens / 1000.0) * out_price_1k

        return round(in_cost + out_cost, 6)

    @staticmethod
    def format_cost(cost: Optional[float]) -> str:
        """Format cost for UI display or state 'Cost unavailable'."""
        if cost is None:
            return "Cost unavailable"
        if cost == 0.0:
            return "$0.000000 (Free / Local)"
        return f"${cost:.6f}"
