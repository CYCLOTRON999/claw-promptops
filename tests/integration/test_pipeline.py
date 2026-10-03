"""Integration tests for the complete generation, caching, fallback, and API pipeline."""

import httpx
import pytest

from app.cache.cache import default_cache
from app.generation.generator import PromptOpsGenerator
from app.main import app


@pytest.mark.asyncio
async def test_end_to_end_successful_generation():
    generator = PromptOpsGenerator()
    resp = await generator.execute(
        task_type="event_brief",
        prompt_name="event_brief",
        prompt_version="v1.0",
        variables={"instruction": "Plan a 3-day Delhi cultural and food trip."},
        preferred_model="mock-deterministic"
    )
    assert resp.status == "SUCCESS"
    assert resp.provider == "mock"
    assert resp.model == "mock-deterministic"
    assert resp.structured_output is not None
    assert "event_name" in resp.structured_output
    assert "date" in resp.structured_output
    assert "location" in resp.structured_output
    assert "description" in resp.structured_output
    assert resp.latency_ms > 0
    assert resp.input_tokens > 0


@pytest.mark.asyncio
async def test_end_to_end_caching():
    default_cache.clear()
    generator = PromptOpsGenerator(cache=default_cache)

    req_args = {
        "task_type": "event_brief",
        "prompt_name": "event_brief",
        "prompt_version": "v2.0",
        "variables": {"instruction": "Plan a 2-day Jaipur trip."},
        "preferred_model": "mock-deterministic",
        "temperature": 0.0
    }

    # First execution: Cache MISS
    resp1 = await generator.execute(**req_args)
    assert resp1.status == "SUCCESS"
    assert resp1.cached is False

    # Second identical execution: Cache HIT
    resp2 = await generator.execute(**req_args)
    assert resp2.status == "SUCCESS"
    assert resp2.cached is True

    stats = default_cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["size"] >= 1


@pytest.mark.asyncio
async def test_end_to_end_repair_flow():
    generator = PromptOpsGenerator()
    resp = await generator.execute(
        task_type="event_brief",
        prompt_name="event_brief",
        prompt_version="v1.0",
        variables={
            "instruction": "Plan trip with simulated missing fields",
            "mock_scenario": "MOCK_MISSING_FIELD"
        },
        metadata={"mock_scenario": "MOCK_MISSING_FIELD"},
        preferred_model="mock-deterministic"
    )

    assert resp.status == "REPAIRED"
    assert resp.repair_count >= 1
    assert resp.structured_output is not None
    assert "event_name" in resp.structured_output


@pytest.mark.asyncio
async def test_end_to_end_fallback_flow():
    generator = PromptOpsGenerator()
    resp = await generator.execute(
        task_type="event_brief",
        prompt_name="event_brief",
        prompt_version="v1.0",
        variables={
            "instruction": "Simulate primary timeout and activate fallback",
            "mock_scenario": "MOCK_TIMEOUT"
        },
        metadata={"mock_scenario": "MOCK_TIMEOUT"},
        preferred_model="mock-deterministic",
        timeout=0.05
    )

    assert resp.status in ("SUCCESS", "REPAIRED")
    assert resp.fallback_used is True
    assert resp.fallback_model == "mock-fallback"


@pytest.mark.asyncio
async def test_api_generate_and_metrics_flow():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # POST /generate
        gen_res = await client.post("/api/v1/generate", json={
            "task_type": "event_brief",
            "prompt_name": "event_brief",
            "prompt_version": "v1.0",
            "variables": {"instruction": "Plan an executive summit in Mumbai."},
            "model": "mock-deterministic"
        })
        assert gen_res.status_code == 200
        gen_data = gen_res.json()
        assert gen_data["status"] in ("SUCCESS", "REPAIRED")
        assert gen_data["structured_output"]["location"] is not None

        # GET /metrics
        metrics_res = await client.get("/api/v1/metrics")
        assert metrics_res.status_code == 200
        metrics = metrics_res.json()
        assert metrics["total_runs"] >= 1
        assert metrics["schema_validity_pct"] > 0
