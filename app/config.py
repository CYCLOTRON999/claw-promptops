"""Centralized configuration for CLAW PromptOps using Pydantic Settings."""

import os
from typing import Dict, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelPricingConfig(BaseSettings):
    """Model token pricing per 1,000 tokens (USD)."""
    input_price_per_1k: float = 0.0
    output_price_per_1k: float = 0.0


DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "mock-deterministic": {"input_price_per_1k": 0.0, "output_price_per_1k": 0.0},
    "mock-fallback": {"input_price_per_1k": 0.0, "output_price_per_1k": 0.0},
    "ollama-llama3": {"input_price_per_1k": 0.0, "output_price_per_1k": 0.0},  # Local compute
    "ollama-mistral": {"input_price_per_1k": 0.0, "output_price_per_1k": 0.0},
    "gpt-3.5-turbo": {"input_price_per_1k": 0.0005, "output_price_per_1k": 0.0015},
    "gpt-4o-mini": {"input_price_per_1k": 0.00015, "output_price_per_1k": 0.0006},
    "gpt-4o": {"input_price_per_1k": 0.005, "output_price_per_1k": 0.015},
}


class Settings(BaseSettings):
    """Application-wide settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application
    app_name: str = "CLAW PromptOps"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # Server Configuration
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Persistence
    database_url: str = "sqlite:///./claw_promptops.db"

    # Generation Defaults
    default_model: str = "mock-deterministic"
    model_timeout_seconds: float = 30.0
    max_retries: int = 2
    max_repair_attempts: int = 2
    cache_enabled: bool = True

    # Provider Endpoints & Credentials
    ollama_base_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: Optional[str] = None

    # Pricing map
    model_pricing: Dict[str, Dict[str, float]] = Field(default_factory=lambda: DEFAULT_PRICING.copy())

    def get_pricing_for_model(self, model_name: str) -> Optional[Dict[str, float]]:
        """Return pricing dictionary if known, else None."""
        return self.model_pricing.get(model_name)


# Global settings instance
settings = Settings()
