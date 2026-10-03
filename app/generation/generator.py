"""Core PromptOps generation coordinator tying together routing, rendering, execution, retry, fallback, validation, repair, and caching."""

import logging
import time
from typing import Any, Dict, Optional
from app.adapters import get_adapter
from app.adapters.base import GenerationRequest, GenerationResponse
from app.cache.cache import default_cache
from app.config import settings
from app.generation.fallback import FallbackHandler
from app.generation.retry import RetryEngine
from app.generation.timeout import execute_with_timeout, ModelTimeoutError
from app.prompts.registry import default_prompt_registry, PromptRegistryError
from app.prompts.renderer import PromptVariableError
from app.routing.router import ModelRouter, RoutingCriteria, RoutingDecision
from app.validation.parser import JSONParser, JSONParseError
from app.validation.json_validator import SchemaValidator, ValidationResult
from app.validation.repair import RepairEngine

logger = logging.getLogger("claw.generator")


class PromptOpsGenerator:
    """Master generation pipeline implementing the full PromptOps reliability workflow."""

    def __init__(self, cache=None, registry=None):
        self.cache = cache or default_cache
        self.registry = registry or default_prompt_registry

    async def execute(
        self,
        task_type: str,
        prompt_name: str,
        prompt_version: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        preferred_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        routing_criteria: Optional[RoutingCriteria] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GenerationResponse:
        """Execute a controlled structured generation through the complete PromptOps pipeline."""
        start_pipeline_time = time.perf_counter()
        variables = variables or {}
        metadata = dict(metadata or {})
        timeout_seconds = timeout or settings.model_timeout_seconds

        # 1. Retrieve prompt definition from registry
        try:
            prompt_def = self.registry.get_prompt(prompt_name, prompt_version)
        except PromptRegistryError as exc:
            return GenerationResponse(
                text="",
                model=preferred_model or settings.default_model,
                provider="unknown",
                status="FAILED",
                error=f"Prompt Registry Error: {str(exc)}"
            )

        # 2. Strict variable validation & rendering
        try:
            rendered_prompt = self.registry.render_prompt(prompt_name, prompt_def.version, variables)
        except PromptVariableError as exc:
            return GenerationResponse(
                text="",
                model=preferred_model or settings.default_model,
                provider="unknown",
                status="FAILED",
                error=f"Prompt Rendering Error: {str(exc)}"
            )

        # 3. Model routing decision
        criteria = routing_criteria or RoutingCriteria(
            task_type=task_type or prompt_def.task_type,
            preferred_model=preferred_model
        )
        routing_decision = ModelRouter.route(criteria)
        selected_model = routing_decision.selected_model
        routing_reason = routing_decision.routing_reason

        # Resolve target parameters
        effective_temp = temperature if temperature is not None else prompt_def.model_requirements.temperature
        effective_max_tokens = max_tokens or prompt_def.model_requirements.max_tokens
        effective_format = prompt_def.model_requirements.response_format or "json"

        # 4. Configuration-aware cache lookup
        cache_key = self.cache.compute_cache_key(
            task_type=task_type,
            prompt_name=prompt_name,
            prompt_version=prompt_def.version,
            rendered_prompt=rendered_prompt,
            model=selected_model,
            temperature=effective_temp,
            max_tokens=effective_max_tokens,
            response_format=effective_format
        )

        cached_response = self.cache.get(cache_key)
        if cached_response is not None:
            cached_response.metadata["routing_reason"] = routing_reason
            cached_response.metadata["cache_status"] = "HIT"
            return cached_response

        # 5. Build strongly-typed GenerationRequest
        gen_request = GenerationRequest(
            task_type=task_type,
            prompt=rendered_prompt,
            variables=variables,
            model=selected_model,
            temperature=effective_temp,
            max_tokens=effective_max_tokens,
            response_format=effective_format,
            timeout=timeout_seconds,
            metadata={
                **metadata,
                "routing_reason": routing_reason,
                "prompt_name": prompt_name,
                "prompt_version": prompt_def.version
            }
        )

        primary_adapter = get_adapter(selected_model)
        primary_response: Optional[GenerationResponse] = None
        primary_failed = False
        primary_error_msg = ""
        retries_used = 0

        # 6. Execute model call wrapped with Retry and Timeout
        async def call_model():
            return await execute_with_timeout(
                primary_adapter.generate(gen_request),
                timeout_seconds=timeout_seconds,
                model=selected_model
            )

        try:
            primary_response, retries_used, _ = await RetryEngine.execute_with_retry(
                operation=call_model,
                max_retries=settings.max_retries,
                task_label=f"generate_{selected_model}"
            )
        except Exception as exc:
            primary_failed = True
            primary_error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.warning(f"Primary model '{selected_model}' generation failed: {primary_error_msg}")

        # 7. Fallback execution if primary failed
        if primary_failed or primary_response is None:
            primary_response = await FallbackHandler.execute_fallback(
                request=gen_request,
                primary_error=primary_error_msg,
                fallback_models=routing_decision.fallback_models
            )
            primary_response.retry_count = retries_used

        if primary_response.status == "FAILED":
            # Generation failed completely across primary & fallbacks
            return primary_response

        # Attach metadata
        primary_response.retry_count = retries_used

        # 8. If unstructured text requested, return directly
        if effective_format != "json":
            self.cache.set(cache_key, primary_response)
            return primary_response

        # 9. Structured JSON parsing & extraction
        schema_path = prompt_def.output_schema
        parsed_json = None
        parse_error: Optional[str] = None

        try:
            parsed_json, _ = JSONParser.extract_and_parse(primary_response.text)
        except JSONParseError as exc:
            parse_error = str(exc)

        # 10. Schema Validation
        if parse_error:
            val_result = ValidationResult(
                is_valid=False,
                errors=[f"JSON Parsing Error: {parse_error}"],
                error_type="JSON_PARSE_ERROR"
            )
        else:
            val_result = SchemaValidator.validate(
                data=parsed_json,
                schema_path_or_dict=schema_path,
                task_type=task_type
            )

        # 11. Repair loop if validation failed
        final_response = primary_response
        if not val_result.is_valid:
            active_adapter = get_adapter(final_response.model)
            final_response, val_result = await RepairEngine.repair_generation(
                adapter=active_adapter,
                request=gen_request,
                initial_response=primary_response,
                initial_validation=val_result,
                schema_path_or_dict=schema_path,
                max_repair_attempts=settings.max_repair_attempts
            )

        if val_result.is_valid:
            final_response.structured_output = val_result.data
            final_response.status = "REPAIRED" if final_response.repair_count > 0 else "SUCCESS"
            # Store in cache
            self.cache.set(cache_key, final_response)
        else:
            final_response.status = "FAILED"
            final_response.error = f"Schema validation failed: {'; '.join(val_result.errors)}"

        total_elapsed_ms = round((time.perf_counter() - start_pipeline_time) * 1000.0, 2)
        final_response.latency_ms = max(final_response.latency_ms, total_elapsed_ms)
        final_response.metadata["routing_reason"] = routing_reason

        return final_response
