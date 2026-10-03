"""Unit tests for JSON parser, SchemaValidator, and RepairEngine."""

import pytest
from app.adapters.base import GenerationRequest, GenerationResponse
from app.adapters.mock import MockAdapter
from app.validation.parser import JSONParser, JSONParseError
from app.validation.json_validator import SchemaValidator, ValidationResult
from app.validation.repair import RepairEngine


def test_parser_clean_json():
    raw = '{"event_name": "Delhi Tech Summit", "date": "2026-11-15", "location": "Delhi", "description": "Tech conference"}'
    parsed, _ = JSONParser.extract_and_parse(raw)
    assert parsed["event_name"] == "Delhi Tech Summit"


def test_parser_markdown_code_blocks():
    raw = """Here is your requested structured brief:
```json
{
  "event_name": "AI Workshop",
  "date": "2026-12-01",
  "location": "Bengaluru",
  "description": "Deep learning hands-on workshop"
}
```
Let me know if you need changes!"""
    parsed, _ = JSONParser.extract_and_parse(raw)
    assert parsed["event_name"] == "AI Workshop"
    assert parsed["location"] == "Bengaluru"


def test_parser_malformed_json_raises():
    raw = '{"event_name": "Unterminated string, "date": 2026}'
    with pytest.raises(JSONParseError):
        JSONParser.extract_and_parse(raw)


def test_schema_validator_valid_event_brief():
    data = {
        "event_name": "PyCon India 2026",
        "date": "2026-09-20",
        "location": "Hyderabad",
        "description": "National Python conference for developers"
    }
    result = SchemaValidator.validate(data, "schemas/event_brief.json", task_type="event_brief")
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_schema_validator_missing_fields():
    data = {
        "date": "2026-09-20",
        "location": "Hyderabad"
    }
    result = SchemaValidator.validate(data, "schemas/event_brief.json", task_type="event_brief")
    assert result.is_valid is False
    assert result.error_type == "MISSING_FIELD"
    assert any("event_name" in err for err in result.errors)


def test_schema_validator_wrong_types():
    data = {
        "event_name": 12345,
        "date": ["invalid", "date"],
        "location": True,
        "description": 999
    }
    result = SchemaValidator.validate(data, "schemas/event_brief.json", task_type="event_brief")
    assert result.is_valid is False
    assert result.error_type == "WRONG_TYPE"


@pytest.mark.asyncio
async def test_repair_engine_successful_recovery():
    adapter = MockAdapter("mock-deterministic")
    req = GenerationRequest(
        task_type="event_brief",
        prompt="Plan a Delhi food trip",
        variables={"instruction": "Plan a Delhi food trip"},
        model="mock-deterministic"
    )

    # Initial invalid response
    broken_response = GenerationResponse(
        text='{"date": "2026-11-15", "location": "Delhi"}',
        model="mock-deterministic",
        provider="mock",
        finish_reason="stop",
        status="FAILED",
        latency_ms=10.0
    )
    initial_val = ValidationResult(
        is_valid=False,
        errors=["Field 'event_name': Field required", "Field 'description': Field required"],
        error_type="MISSING_FIELD"
    )

    final_resp, final_val = await RepairEngine.repair_generation(
        adapter=adapter,
        request=req,
        initial_response=broken_response,
        initial_validation=initial_val,
        schema_path_or_dict="schemas/event_brief.json",
        max_repair_attempts=2
    )

    assert final_val.is_valid is True
    assert final_resp.status == "REPAIRED"
    assert final_resp.repair_count == 1
    assert final_resp.structured_output["event_name"] is not None
