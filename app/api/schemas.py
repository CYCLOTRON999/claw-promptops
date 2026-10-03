"""API request and response schemas for CLAW PromptOps."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.adapters.base import ModelInfo


class HealthResponse(BaseModel):
    """System health and operational status."""
    status: str = Field(default="healthy", description="Operational health status")
    app_name: str
    version: str
    default_model: str
    cache_enabled: bool
    available_models: List[str]


class GenerateApiRequest(BaseModel):
    """Payload for POST /generate and /generate/stream."""
    task_type: str = Field(default="event_brief", description="Task classification name")
    prompt_name: str = Field(default="event_brief", description="Target registered prompt")
    prompt_version: Optional[str] = Field(default="latest", description="Version identifier or 'latest'")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables to render into the prompt")
    model: Optional[str] = Field(default=None, description="Model override or None for auto-routing")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    timeout: Optional[float] = Field(default=None, gt=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidateApiRequest(BaseModel):
    """Payload for POST /validate."""
    data: Any = Field(..., description="Parsed JSON object or dictionary to validate")
    schema_path: Optional[str] = Field(default=None, description="Path to JSON Schema file")
    task_type: Optional[str] = Field(default=None, description="Task type for Pydantic validation")


class RunExperimentApiRequest(BaseModel):
    """Payload for triggering comparative prompt/model experiments."""
    name: str = Field(..., description="Descriptive experiment title")
    prompt_name: str = Field(default="event_brief")
    prompt_version_a: str = Field(default="v1.0")
    prompt_version_b: str = Field(default="v2.0")
    model_a: str = Field(default="mock-deterministic")
    model_b: str = Field(default="mock-deterministic")
    test_case_ids: Optional[List[str]] = Field(default=None, description="Subset of test case IDs to run")


class PromptVersionSummary(BaseModel):
    """Summary of a registered prompt version."""
    name: str
    version: str
    description: str
    task_type: str
    output_schema: Optional[str] = None
    creation_date: str
    change_description: str
    variables: List[Dict[str, Any]]
