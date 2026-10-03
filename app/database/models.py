"""SQLAlchemy 2.0 database models for CLAW PromptOps."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RunRecordModel(Base):
    """Auditable log of an individual model generation execution."""
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    prompt_name: Mapped[str] = mapped_column(String(128), index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), index=True)
    rendered_prompt: Mapped[str] = mapped_column(Text)
    user_input: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)
    structured_output_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)  # SUCCESS, FAILED, REPAIRED

    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    error_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experiment_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)


class ExperimentModel(Base):
    """Specification and aggregate comparison results for a Prompt/Model benchmark."""
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED")  # RUNNING, COMPLETED, FAILED

    prompt_a_name: Mapped[str] = mapped_column(String(128))
    prompt_a_version: Mapped[str] = mapped_column(String(32))
    prompt_b_name: Mapped[str] = mapped_column(String(128))
    prompt_b_version: Mapped[str] = mapped_column(String(32))

    model_a: Mapped[str] = mapped_column(String(64))
    model_b: Mapped[str] = mapped_column(String(64))

    summary_metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FailureLogModel(Base):
    """Dedicated failure log table capturing diagnostic context for regressions and outages."""
    __tablename__ = "failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    task_type: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    failure_type: Mapped[str] = mapped_column(String(64), index=True)
    error_message: Mapped[str] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TestCaseModel(Base):
    """Persistent storage for regression test suite definitions."""
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g., TC001
    category: Mapped[str] = mapped_column(String(64), index=True)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(String(256))
    input_text: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text)
    expected_json: Mapped[str] = mapped_column(Text)
