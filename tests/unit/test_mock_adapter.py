"""Unit tests for MockAdapter deterministic generation, failure simulations, and streaming."""

import asyncio
import json
import pytest

from app.adapters.base import GenerationRequest
from app.adapters.mock import MockAdapter, MockAdapterError


@pytest.mark.asyncio
async def test_mock_adapter_metadata():
    adapter = MockAdapter("mock-deterministic")
    info = adapter.get_model_info()
    assert info.name == "mock-deterministic"
    assert info.provider == "mock"
    assert info.is_mock is True
    assert info.supports_structured is True
    assert info.supports_streaming is True
    assert info.input_price_per_1k == 0.0
    assert info.output_price_per_1k == 0.0


@pytest.mark.asyncio
async def test_mock_adapter_valid_generation():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Plan a 3-day Delhi trip with food and culture.",
        variables={"instruction": "Plan a 3-day Delhi trip"},
        model="mock-deterministic",
        temperature=0.0
    )
    res = await adapter.generate(req)
    assert res.status == "SUCCESS"
    assert res.provider == "mock"
    assert res.model == "mock-deterministic"
    assert res.finish_reason == "stop"
    assert res.input_tokens > 0
    assert res.output_tokens > 0
    assert res.latency_ms >= 0

    # Ensure output is valid JSON adhering to event_brief expectations
    parsed = json.loads(res.text)
    assert "event_name" in parsed
    assert "date" in parsed
    assert "location" in parsed
    assert "description" in parsed


@pytest.mark.asyncio
async def test_mock_adapter_malformed_json_scenario():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Generate event brief",
        metadata={"mock_scenario": "MOCK_MALFORMED_JSON"},
        model="mock-deterministic"
    )
    res = await adapter.generate(req)
    # Text should not be valid JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(res.text)


@pytest.mark.asyncio
async def test_mock_adapter_missing_field_scenario():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Generate event brief",
        metadata={"mock_scenario": "MOCK_MISSING_FIELD"},
        model="mock-deterministic"
    )
    res = await adapter.generate(req)
    parsed = json.loads(res.text)
    assert "event_name" not in parsed
    assert "description" not in parsed
    assert "location" in parsed


@pytest.mark.asyncio
async def test_mock_adapter_wrong_type_scenario():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Generate event brief",
        metadata={"mock_scenario": "MOCK_WRONG_TYPE"},
        model="mock-deterministic"
    )
    res = await adapter.generate(req)
    parsed = json.loads(res.text)
    assert isinstance(parsed["event_name"], int)
    assert isinstance(parsed["date"], list)


@pytest.mark.asyncio
async def test_mock_adapter_timeout_scenario():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Simulate timeout",
        metadata={"mock_scenario": "MOCK_TIMEOUT"},
        model="mock-deterministic",
        timeout=0.05
    )
    with pytest.raises(asyncio.TimeoutError):
        await adapter.generate(req)


@pytest.mark.asyncio
async def test_mock_adapter_provider_error_scenario():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Simulate 503",
        metadata={"mock_scenario": "MOCK_PROVIDER_ERROR"},
        model="mock-deterministic"
    )
    with pytest.raises(MockAdapterError):
        await adapter.generate(req)


@pytest.mark.asyncio
async def test_mock_adapter_repair_recovery():
    adapter = MockAdapter("mock-deterministic")
    # Even if previous scenario was broken, repair attempt restores validity
    req = GenerationRequest(
        task_type="event_brief",
        prompt="REPAIR ATTEMPT: Fix previously malformed output",
        metadata={"mock_scenario": "MOCK_MALFORMED_JSON", "is_repair": True},
        model="mock-deterministic"
    )
    res = await adapter.generate(req)
    parsed = json.loads(res.text)
    assert "event_name" in parsed
    assert "date" in parsed


@pytest.mark.asyncio
async def test_mock_adapter_streaming():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Stream event brief",
        model="mock-deterministic"
    )
    chunks = []
    async for chunk in adapter.stream(req):
        chunks.append(chunk.text)

    assembled = "".join(chunks)
    parsed = json.loads(assembled)
    assert "event_name" in parsed
    assert "location" in parsed


@pytest.mark.asyncio
async def test_mock_adapter_streaming_interrupted():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Stream with interruption",
        metadata={"mock_scenario": "MOCK_INTERRUPTED_STREAM"},
        model="mock-deterministic"
    )
    chunks = []
    with pytest.raises(MockAdapterError):
        async for chunk in adapter.stream(req):
            chunks.append(chunk.text)

    assert len(chunks) > 0  # Received partial response before failure
