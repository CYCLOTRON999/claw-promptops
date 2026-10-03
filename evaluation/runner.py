"""Regression evaluation runner executing fixed test suites against the PromptOps pipeline."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.database.database import SessionLocal, init_db
from app.database.repositories import RunRepository, FailureRepository, TestCaseRepository
from app.generation.generator import PromptOpsGenerator
from app.metrics.evaluator import InstructionEvaluator, EvaluationReport
from app.metrics.cost import CostCalculator


class EvaluationSuiteRunner:
    """Executes deterministic test suites and aggregates verifiable benchmark metrics."""

    def __init__(self, test_cases_path: Optional[Path] = None, generator: Optional[PromptOpsGenerator] = None):
        self.test_cases_path = test_cases_path or (Path(__file__).parent / "test_cases.json")
        self.generator = generator or PromptOpsGenerator()
        from app.prompts.registry import default_prompt_registry
        default_prompt_registry.reload()
        init_db()

    def load_test_cases(self) -> List[Dict[str, Any]]:
        with open(self.test_cases_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def seed_database(self, db: Optional[Session] = None) -> int:
        test_cases = self.load_test_cases()
        session = db or SessionLocal()
        try:
            return TestCaseRepository.upsert_test_cases(session, test_cases)
        finally:
            if db is None:
                session.close()

    async def run_test(
        self,
        test_case: Dict[str, Any],
        model: Optional[str] = None,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Execute a single test case through the complete pipeline and evaluate adherence."""
        tc_id = test_case["id"]
        task_type = test_case["task_type"]
        variables = dict(test_case.get("variables", {}))
        expected = test_case.get("expected", {})

        # Default prompt resolution
        target_prompt = prompt_name or task_type
        target_version = prompt_version or "latest"
        try:
            from app.prompts.registry import default_prompt_registry
            default_prompt_registry.get_prompt(target_prompt, target_version)
        except Exception:
            target_version = "latest"

        # Execute through PromptOps pipeline
        response = await self.generator.execute(
            task_type=task_type,
            prompt_name=target_prompt,
            prompt_version=target_version,
            variables=variables,
            preferred_model=model,
            metadata={"test_id": tc_id, "category": test_case.get("category")}
        )

        # Evaluate instruction following
        eval_report: EvaluationReport = InstructionEvaluator.evaluate(
            output_dict=response.structured_output,
            raw_text=response.text,
            expected=expected
        )

        # Determine pass/fail based on schema validity and instruction adherence
        is_passed = (response.status in ("SUCCESS", "REPAIRED")) and eval_report.passed

        # Persist run record to SQLite
        session = db or SessionLocal()
        try:
            run_data = {
                "id": f"RUN-{tc_id}-{int(response.latency_ms*100)}",
                "task_type": task_type,
                "prompt_name": target_prompt,
                "prompt_version": response.metadata.get("prompt_version", "v1.0"),
                "rendered_prompt": response.metadata.get("rendered_prompt", response.text),
                "user_input": test_case["input_text"],
                "output_text": response.text,
                "structured_output_json": json.dumps(response.structured_output) if response.structured_output else None,
                "model": response.model,
                "provider": response.provider,
                "status": "SUCCESS" if is_passed else "FAILED",
                "latency_ms": response.latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.input_tokens + response.output_tokens,
                "estimated_cost": response.estimated_cost,
                "cached": response.cached,
                "retry_count": response.retry_count,
                "repair_count": response.repair_count,
                "fallback_used": response.fallback_used,
                "fallback_model": response.fallback_model,
                "error_type": response.error,
                "error_message": "; ".join(eval_report.details) if not is_passed else None
            }
            RunRepository.save_run(session, run_data)

            # If failed, log to dedicated failure table
            if not is_passed:
                FailureRepository.record_failure(session, {
                    "run_id": run_data["id"],
                    "task_type": task_type,
                    "model": response.model,
                    "prompt_version": run_data["prompt_version"],
                    "failure_type": "VALIDATION_ERROR" if not response.structured_output else "INSTRUCTION_VIOLATION",
                    "error_message": "; ".join(eval_report.details),
                    "retry_count": response.retry_count,
                    "repair_count": response.repair_count,
                    "fallback_used": response.fallback_used,
                    "raw_payload": response.text
                })
        finally:
            if db is None:
                session.close()

        return {
            "test_id": tc_id,
            "category": test_case.get("category"),
            "passed": is_passed,
            "status": response.status,
            "latency_ms": response.latency_ms,
            "tokens": response.input_tokens + response.output_tokens,
            "cost": response.estimated_cost,
            "repair_count": response.repair_count,
            "retry_count": response.retry_count,
            "fallback_used": response.fallback_used,
            "evaluation_score": eval_report.score,
            "details": eval_report.details,
            "structured_output": response.structured_output
        }

    async def run_suite(
        self,
        test_ids: Optional[List[str]] = None,
        model: Optional[str] = None,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a full regression benchmark across all or filtered test cases."""
        test_cases = self.load_test_cases()
        if test_ids:
            test_cases = [tc for tc in test_cases if tc["id"] in test_ids]

        results = []
        total_latency = 0.0
        total_tokens = 0
        total_cost = 0.0
        passed_count = 0
        valid_schema_count = 0
        repair_count = 0
        retry_count = 0
        fallback_count = 0

        session = SessionLocal()
        try:
            for tc in test_cases:
                res = await self.run_test(
                    test_case=tc,
                    model=model,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    db=session
                )
                results.append(res)

                if res["passed"]:
                    passed_count += 1
                if res["structured_output"] is not None:
                    valid_schema_count += 1
                if res["repair_count"] > 0:
                    repair_count += 1
                if res["retry_count"] > 0:
                    retry_count += 1
                if res["fallback_used"]:
                    fallback_count += 1

                total_latency += res["latency_ms"]
                total_tokens += res["tokens"]
                if res["cost"]:
                    total_cost += res["cost"]
        finally:
            session.close()

        total = len(test_cases)
        return {
            "total_tests": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate_pct": round((passed_count / total * 100.0) if total else 0.0, 2),
            "schema_validity_pct": round((valid_schema_count / total * 100.0) if total else 0.0, 2),
            "avg_latency_ms": round((total_latency / total) if total else 0.0, 2),
            "avg_tokens": round((total_tokens / total) if total else 0.0, 1),
            "total_cost_usd": round(total_cost, 6),
            "repair_rate_pct": round((repair_count / total * 100.0) if total else 0.0, 2),
            "retry_rate_pct": round((retry_count / total * 100.0) if total else 0.0, 2),
            "fallback_rate_pct": round((fallback_count / total * 100.0) if total else 0.0, 2),
            "test_results": results
        }
