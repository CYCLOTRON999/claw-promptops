"""Regression test suite validating all 50+ fixed evaluation test cases."""

import pytest
from evaluation.runner import EvaluationSuiteRunner


def test_test_cases_count_and_distribution():
    runner = EvaluationSuiteRunner()
    test_cases = runner.load_test_cases()
    assert len(test_cases) >= 50, f"Expected at least 50 fixed test cases, found {len(test_cases)}"

    categories = set(tc["category"] for tc in test_cases)
    expected_categories = {
        "normal",
        "malformed_json",
        "missing_fields",
        "wrong_type",
        "contradictory_instructions",
        "long_input",
        "empty_input",
        "timeout_simulation",
        "interrupted_stream",
        "edge_case"
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"


@pytest.mark.asyncio
async def test_full_50_suite_execution():
    runner = EvaluationSuiteRunner()
    results = await runner.run_suite(model="mock-deterministic", prompt_version="v2.0")

    assert results["total_tests"] >= 50
    assert results["schema_validity_pct"] >= 95.0
    assert results["pass_rate_pct"] >= 90.0
    assert results["avg_latency_ms"] >= 0.0
    assert results["avg_tokens"] > 0
    assert len(results["test_results"]) == results["total_tests"]
