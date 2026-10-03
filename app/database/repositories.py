"""Repository data-access patterns for Runs, Failures, Experiments, and Test Cases."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from app.database.models import RunRecordModel, FailureLogModel, ExperimentModel, TestCaseModel


class RunRepository:
    """Manages persistence and query analytics for generation runs."""

    @staticmethod
    def save_run(db: Session, run_data: Dict[str, Any]) -> RunRecordModel:
        run = RunRecordModel(**run_data)
        db.merge(run)
        db.commit()
        return run

    @staticmethod
    def get_run(db: Session, run_id: str) -> Optional[RunRecordModel]:
        return db.scalar(select(RunRecordModel).where(RunRecordModel.id == run_id))

    @staticmethod
    def list_runs(db: Session, limit: int = 50, offset: int = 0) -> List[RunRecordModel]:
        stmt = select(RunRecordModel).order_by(desc(RunRecordModel.timestamp)).limit(limit).offset(offset)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_aggregate_metrics(db: Session) -> Dict[str, Any]:
        """Compute real, verified aggregate metrics across all runs."""
        total_runs = db.scalar(select(func.count(RunRecordModel.id))) or 0
        if total_runs == 0:
            return {
                "total_runs": 0,
                "success_rate_pct": 0.0,
                "schema_validity_pct": 0.0,
                "avg_latency_ms": 0.0,
                "avg_tokens": 0.0,
                "total_cost_usd": 0.0,
                "repair_rate_pct": 0.0,
                "failure_rate_pct": 0.0,
                "cache_hit_rate_pct": 0.0,
            }

        success_count = db.scalar(
            select(func.count(RunRecordModel.id)).where(RunRecordModel.status.in_(["SUCCESS", "REPAIRED"]))
        ) or 0
        repaired_count = db.scalar(
            select(func.count(RunRecordModel.id)).where(RunRecordModel.status == "REPAIRED")
        ) or 0
        failed_count = db.scalar(
            select(func.count(RunRecordModel.id)).where(RunRecordModel.status == "FAILED")
        ) or 0
        cached_count = db.scalar(
            select(func.count(RunRecordModel.id)).where(RunRecordModel.cached == True)  # noqa: E712
        ) or 0

        avg_latency = db.scalar(select(func.avg(RunRecordModel.latency_ms))) or 0.0
        avg_tokens = db.scalar(select(func.avg(RunRecordModel.total_tokens))) or 0.0
        total_cost = db.scalar(select(func.sum(RunRecordModel.estimated_cost))) or 0.0

        return {
            "total_runs": total_runs,
            "success_rate_pct": round((success_count / total_runs) * 100.0, 2),
            "schema_validity_pct": round((success_count / total_runs) * 100.0, 2),
            "avg_latency_ms": round(float(avg_latency), 2),
            "avg_tokens": round(float(avg_tokens), 1),
            "total_cost_usd": round(float(total_cost), 6),
            "repair_rate_pct": round((repaired_count / total_runs) * 100.0, 2),
            "failure_rate_pct": round((failed_count / total_runs) * 100.0, 2),
            "cache_hit_rate_pct": round((cached_count / total_runs) * 100.0, 2),
        }


class FailureRepository:
    """Logs and queries diagnostic failure records."""

    @staticmethod
    def record_failure(db: Session, failure_data: Dict[str, Any]) -> FailureLogModel:
        failure = FailureLogModel(**failure_data)
        db.add(failure)
        db.commit()
        db.refresh(failure)
        return failure

    @staticmethod
    def list_failures(db: Session, limit: int = 50) -> List[FailureLogModel]:
        stmt = select(FailureLogModel).order_by(desc(FailureLogModel.timestamp)).limit(limit)
        return list(db.scalars(stmt).all())


class ExperimentRepository:
    """Stores and queries side-by-side benchmark experiments."""

    @staticmethod
    def save_experiment(db: Session, experiment_data: Dict[str, Any]) -> ExperimentModel:
        exp = ExperimentModel(**experiment_data)
        db.merge(exp)
        db.commit()
        return exp

    @staticmethod
    def get_experiment(db: Session, experiment_id: str) -> Optional[ExperimentModel]:
        return db.scalar(select(ExperimentModel).where(ExperimentModel.id == experiment_id))

    @staticmethod
    def list_experiments(db: Session, limit: int = 50) -> List[ExperimentModel]:
        stmt = select(ExperimentModel).order_by(desc(ExperimentModel.created_at)).limit(limit)
        return list(db.scalars(stmt).all())


class TestCaseRepository:
    """Stores fixed regression test cases."""

    @staticmethod
    def upsert_test_cases(db: Session, test_cases: List[Dict[str, Any]]) -> int:
        count = 0
        for tc in test_cases:
            model = TestCaseModel(
                id=tc["id"],
                category=tc["category"],
                task_type=tc["task_type"],
                description=tc["description"],
                input_text=tc["input_text"],
                variables_json=json.dumps(tc.get("variables", {})),
                expected_json=json.dumps(tc.get("expected", {}))
            )
            db.merge(model)
            count += 1
        db.commit()
        return count

    @staticmethod
    def list_test_cases(db: Session) -> List[TestCaseModel]:
        stmt = select(TestCaseModel).order_by(TestCaseModel.id)
        return list(db.scalars(stmt).all())
