"""Base adapter interface and request/response contracts for CLAW PromptOps."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """Strongly-typed contract for model generation requests."""
    task_type: str = Field(..., description="Classification/type of task (e.g., event_brief, extraction)")
    prompt: str = Field(..., description="Rendered prompt string to submit to the model")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables used during rendering")
    model: str = Field(..., description="Model identifier (e.g., mock-deterministic, llama3, gpt-4o-mini)")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=1024, gt=0, description="Maximum tokens to generate")
    response_format: Optional[str] = Field(default="json", description="Expected format: 'json' or 'text'")
    json_schema: Optional[Dict[str, Any]] = Field(default=None, description="Optional target JSON Schema")
    timeout: Optional[float] = Field(default=30.0, gt=0.0, description="Request timeout in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary tracing metadata (run_id, test_id)")
    stream: bool = Field(default=False, description="Whether to stream tokens")


class StreamChunk(BaseModel):
    """Individual streamed chunk containing text fragment and optional finish state."""
    text: str
    finish_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class GenerationResponse(BaseModel):
    """Strongly-typed contract for model generation responses."""
    text: str = Field(default="", description="Raw generated text from the model")
    structured_output: Optional[Any] = Field(default=None, description="Validated parsed JSON or object")
    model: str = Field(..., description="Actual model that produced the response")
    provider: str = Field(..., description="Provider name ('mock', 'ollama', 'openai_compatible')")
    finish_reason: str = Field(default="stop", description="Generation termination reason ('stop', 'length', etc.)")
    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens consumed")
    output_tokens: int = Field(default=0, ge=0, description="Completion tokens generated")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Roundtrip model latency in milliseconds")
    estimated_cost: Optional[float] = Field(default=None, description="Calculated USD cost, or None if unknown")
    cached: bool = Field(default=False, description="Whether response was served from cache")
    retry_count: int = Field(default=0, ge=0, description="Number of network/transient retries attempted")
    repair_count: int = Field(default=0, ge=0, description="Number of schema repair attempts performed")
    fallback_used: bool = Field(default=False, description="Whether a fallback model was used")
    fallback_model: Optional[str] = Field(default=None, description="Identifier of fallback model if used")
    status: str = Field(default="SUCCESS", description="Execution outcome: 'SUCCESS', 'FAILED', or 'REPAIRED'")
    error: Optional[str] = Field(default=None, description="Detailed error description if failed")
    raw_response: Optional[str] = Field(default=None, description="Unprocessed raw response payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic and routing metadata")


class ModelInfo(BaseModel):
    """Metadata describing a model's capabilities and pricing."""
    name: str
    provider: str
    supports_structured: bool = True
    supports_streaming: bool = True
    context_window: int = 4096
    input_price_per_1k: Optional[float] = None
    output_price_per_1k: Optional[float] = None
    is_mock: bool = False
    description: str = ""


class BaseModelAdapter(ABC):
    """Abstract base class decoupling LLM providers from the core generation pipeline."""

    def __init__(self, model_name: str, config: Optional[Dict[str, Any]] = None):
        self.model_name = model_name
        self.config = config or {}

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute a non-streaming completion against the model."""
        pass

    @abstractmethod
    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Stream completion tokens asynchronously."""
        pass

    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Whether the provider natively enforces JSON or structured response schemas."""
        pass

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return model metadata, capabilities, and pricing specifications."""
        pass
