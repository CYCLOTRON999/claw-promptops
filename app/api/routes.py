"""API endpoints for CLAW PromptOps."""

import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.adapters import get_adapter, list_available_models
from app.adapters.base import GenerationRequest, GenerationResponse, ModelInfo
from app.api.schemas import (
    GenerateApiRequest,
    HealthResponse,
    PromptVersionSummary,
    RunExperimentApiRequest,
    ValidateApiRequest
)
from app.config import settings
from app.database.database import get_db
from app.database.repositories import (
    ExperimentRepository,
    FailureRepository,
    RunRepository,
    TestCaseRepository
)
from app.experiments.runner import ExperimentRunner
from app.generation.generator import PromptOpsGenerator
from app.prompts.registry import default_prompt_registry, PromptRegistryError
from app.validation.json_validator import SchemaValidator, ValidationResult

router = APIRouter()
generator = PromptOpsGenerator()
experiment_runner = ExperimentRunner()


@router.get("/health", response_model=HealthResponse, summary="System Health & Diagnostic Status")
async def get_health() -> HealthResponse:
    """Return operational readiness, active configuration, and available models."""
    models = list_available_models()
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version=settings.app_version,
        default_model=settings.default_model,
        cache_enabled=settings.cache_enabled,
        available_models=[m.name for m in models]
    )


@router.get("/models", response_model=List[ModelInfo], summary="List Available Model Backends")
async def get_models() -> List[ModelInfo]:
    """Retrieve capability profiles, context limits, and pricing for all configured models."""
    return list_available_models()


@router.get("/prompts", response_model=List[str], summary="List Registered Prompts")
async def list_prompts() -> List[str]:
    """Return all unique registered prompt names."""
    return default_prompt_registry.list_prompts()


@router.get("/prompts/{name}", summary="Get Prompt Details and Versions")
async def get_prompt_details(name: str) -> Dict[str, Any]:
    """Return all version history and variables for a prompt."""
    try:
        versions = default_prompt_registry.list_versions(name)
        history = default_prompt_registry.get_change_history(name)
        return {
            "name": name,
            "versions": versions,
            "latest_version": default_prompt_registry.get_latest_prompt(name).version,
            "history": history
        }
    except PromptRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/prompts/{name}/{version}", response_model=PromptVersionSummary, summary="Get Specific Prompt Version")
async def get_prompt_version(name: str, version: str) -> PromptVersionSummary:
    """Retrieve full specification for an immutable prompt version."""
    try:
        p = default_prompt_registry.get_prompt(name, version)
        return PromptVersionSummary(
            name=p.name,
            version=p.version,
            description=p.description,
            task_type=p.task_type,
            output_schema=p.output_schema,
            creation_date=p.creation_date,
            change_description=p.change_description,
            variables=[v.model_dump() for v in p.variables]
        )
    except PromptRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/generate", response_model=GenerationResponse, summary="Execute Controlled Generation")
async def generate(request: GenerateApiRequest, db: Session = Depends(get_db)) -> GenerationResponse:
    """Run generation request through PromptOps pipeline with validation, repair, and routing."""
    response = await generator.execute(
        task_type=request.task_type,
        prompt_name=request.prompt_name,
        prompt_version=request.prompt_version,
        variables=request.variables,
        preferred_model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        timeout=request.timeout,
        metadata=request.metadata
    )

    # Persist run to SQLite
    run_id = f"RUN-{int(response.latency_ms*100)}-{id(response)}"
    run_data = {
        "id": run_id,
        "task_type": request.task_type,
        "prompt_name": request.prompt_name,
        "prompt_version": request.prompt_version or "latest",
        "rendered_prompt": response.text,
        "user_input": str(request.variables),
        "output_text": response.text,
        "structured_output_json": json.dumps(response.structured_output) if response.structured_output else None,
        "model": response.model,
        "provider": response.provider,
        "status": response.status,
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
        "error_type": response.error
    }
    RunRepository.save_run(db, run_data)

    if response.status == "FAILED":
        FailureRepository.record_failure(db, {
            "run_id": run_id,
            "task_type": request.task_type,
            "model": response.model,
            "prompt_version": request.prompt_version or "latest",
            "failure_type": "GENERATION_FAILURE",
            "error_message": response.error or "Unknown failure",
            "retry_count": response.retry_count,
            "repair_count": response.repair_count,
            "fallback_used": response.fallback_used,
            "raw_payload": response.text
        })

    return response


@router.post("/generate/stream", summary="Execute Streaming Generation")
async def generate_stream(request: GenerateApiRequest):
    """Progressively stream generated tokens via Server-Sent Events."""
    adapter = get_adapter(request.model or settings.default_model)

    rendered_prompt = request.variables.get("instruction", "Stream instruction")
    try:
        rendered_prompt = default_prompt_registry.render_prompt(
            request.prompt_name,
            request.prompt_version,
            request.variables
        )
    except Exception:
        pass

    gen_req = GenerationRequest(
        task_type=request.task_type,
        prompt=rendered_prompt,
        variables=request.variables,
        model=adapter.model_name,
        temperature=request.temperature or 0.0,
        max_tokens=request.max_tokens,
        stream=True
    )

    async def event_generator():
        try:
            async for chunk in adapter.stream(gen_req):
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/validate", response_model=ValidationResult, summary="Validate Output Schema")
async def validate_schema(request: ValidateApiRequest) -> ValidationResult:
    """Directly test validation rules against arbitrary JSON payloads."""
    schema_path = request.schema_path
    if not schema_path and request.task_type == "event_brief":
        schema_path = "schemas/event_brief.json"
    elif not schema_path and request.task_type == "content_pack":
        schema_path = "schemas/content_pack.json"

    return SchemaValidator.validate(
        data=request.data,
        schema_path_or_dict=schema_path,
        task_type=request.task_type
    )


@router.post("/experiments/run", summary="Run Side-by-Side Experiment")
async def run_experiment(req: RunExperimentApiRequest, db: Session = Depends(get_db)):
    """Trigger comparative experiment over identical benchmark cases."""
    report = await experiment_runner.run_comparison(
        name=req.name,
        prompt_name=req.prompt_name,
        prompt_version_a=req.prompt_version_a,
        prompt_version_b=req.prompt_version_b,
        model_a=req.model_a,
        model_b=req.model_b,
        test_case_ids=req.test_case_ids,
        db=db
    )
    return report


@router.get("/experiments", summary="List All Experiments")
async def list_experiments(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve past benchmark experiments."""
    return ExperimentRepository.list_experiments(db, limit=limit)


@router.get("/experiments/{id}", summary="Get Experiment Details")
async def get_experiment(id: str, db: Session = Depends(get_db)):
    """Retrieve full side-by-side comparison report for an experiment."""
    exp = ExperimentRepository.get_experiment(db, id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{id}' not found.")
    return exp


@router.get("/runs", summary="List Historical Runs")
async def list_runs(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Query recent generation run records."""
    return RunRepository.list_runs(db, limit=limit, offset=offset)


@router.get("/runs/{id}", summary="Get Run Audit Record")
async def get_run(id: str, db: Session = Depends(get_db)):
    """Retrieve complete audit trace for an individual run."""
    run = RunRepository.get_run(db, id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{id}' not found.")
    return run


@router.get("/metrics", summary="Get Verifiable Aggregate Metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Compute verified aggregate metrics computed across real database records."""
    return RunRepository.get_aggregate_metrics(db)


@router.get("/failures", summary="List Failure Log Records")
async def list_failures(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieve diagnostic failure events."""
    return FailureRepository.list_failures(db, limit=limit)
