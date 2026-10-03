"""Unit tests for FastAPI /health and /models endpoints."""

import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app_name"] == "CLAW PromptOps"
        assert "mock-deterministic" in data["available_models"]


@pytest.mark.asyncio
async def test_models_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/models")
        assert response.status_code == 200
        models = response.json()
        assert len(models) >= 2
        model_names = [m["name"] for m in models]
        assert "mock-deterministic" in model_names
        assert "mock-fallback" in model_names
