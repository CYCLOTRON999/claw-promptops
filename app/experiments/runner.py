"""Experiment execution engine running identical benchmarks across prompt versions and models."""

import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.database.database import SessionLocal, init_db
from app.database.repositories import ExperimentRepository
from app.experiments.comparison import ExperimentComparator, ExperimentComparisonReport
from evaluation.runner import EvaluationSuiteRunner


class ExperimentRunner:
    """Orchestrates comparative experiments across identical test sets."""

    def __init__(self):
        self.suite_runner = EvaluationSuiteRunner()
        init_db()

    async def run_comparison(
        self,
        name: str,
        prompt_name: str,
        prompt_version_a: str,
        prompt_version_b: str,
        model_a: str,
        model_b: str,
        test_case_ids: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> ExperimentComparisonReport:
        """Run identical test cases through Variant A and Variant B, persisting and comparing results."""
        exp_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"

        # 1. Execute Variant A
        results_a = await self.suite_runner.run_suite(
            test_ids=test_case_ids,
            model=model_a,
            prompt_name=prompt_name,
            prompt_version=prompt_version_a
        )

        # 2. Execute Variant B on identical test cases
        results_b = await self.suite_runner.run_suite(
            test_ids=test_case_ids,
            model=model_b,
            prompt_name=prompt_name,
            prompt_version=prompt_version_b
        )

        metrics_a = {
            "name": f"{model_a} ({prompt_version_a})",
            "prompt_version": prompt_version_a,
            "model": model_a,
            "total_runs": results_a["total_tests"],
            "schema_validity_pct": results_a["schema_validity_pct"],
            "instruction_following_pct": results_a["pass_rate_pct"],
            "avg_latency_ms": results_a["avg_latency_ms"],
            "avg_tokens": results_a["avg_tokens"],
            "total_cost_usd": results_a["total_cost_usd"],
            "repair_rate_pct": results_a["repair_rate_pct"],
            "retry_rate_pct": results_a["retry_rate_pct"],
            "failure_rate_pct": round(100.0 - results_a["pass_rate_pct"], 2),
        }

        metrics_b = {
            "name": f"{model_b} ({prompt_version_b})",
            "prompt_version": prompt_version_b,
            "model": model_b,
            "total_runs": results_b["total_tests"],
            "schema_validity_pct": results_b["schema_validity_pct"],
            "instruction_following_pct": results_b["pass_rate_pct"],
            "avg_latency_ms": results_b["avg_latency_ms"],
            "avg_tokens": results_b["avg_tokens"],
            "total_cost_usd": results_b["total_cost_usd"],
            "repair_rate_pct": results_b["repair_rate_pct"],
            "retry_rate_pct": results_b["retry_rate_pct"],
            "failure_rate_pct": round(100.0 - results_b["pass_rate_pct"], 2),
        }

        report = ExperimentComparator.compare(
            experiment_id=exp_id,
            name=name,
            metrics_a=metrics_a,
            metrics_b=metrics_b
        )

        # Persist experiment to database
        session = db or SessionLocal()
        try:
            ExperimentRepository.save_experiment(session, {
                "id": exp_id,
                "name": name,
                "status": "COMPLETED",
                "prompt_a_name": prompt_name,
                "prompt_a_version": prompt_version_a,
                "prompt_b_name": prompt_name,
                "prompt_b_version": prompt_version_b,
                "model_a": model_a,
                "model_b": model_b,
                "summary_metrics_json": report.model_dump_json()
            })
        finally:
            if db is None:
                session.close()

        return report
