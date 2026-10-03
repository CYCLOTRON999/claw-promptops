"""Prompt repair engine for automated schema correction and error recovery."""

import json
from typing import Any, Dict, List, Optional, Tuple
from app.adapters.base import BaseModelAdapter, GenerationRequest, GenerationResponse
from app.validation.parser import JSONParser, JSONParseError
from app.validation.json_validator import SchemaValidator, ValidationResult


class RepairEngine:
    """Orchestrates structured repair loops when model outputs fail JSON parsing or schema validation."""

    @staticmethod
    def build_repair_prompt(
        original_prompt: str,
        failed_output: str,
        errors: List[str],
        schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """Construct a targeted corrective prompt highlighting specific validation violations."""
        error_bullets = "\n".join(f"- {e}" for e in errors)
        schema_summary = f"\nRequired Schema:\n{json.dumps(schema, indent=2)}" if schema else ""

        repair_prompt = f"""[REPAIR ATTEMPT - VALIDATION ERROR]
The previous output failed structured validation. You must fix the errors below.

Original Instruction:
{original_prompt}

Your Previous Invalid Output:
{failed_output}

Validation Errors Detected:
{error_bullets}
{schema_summary}

Correction Rules:
1. Fix all listed errors immediately.
2. Return ONLY a single raw, parseable JSON object matching the required schema.
3. Include all mandatory fields with correct data types.
4. Do NOT include markdown formatting, conversational commentary, or explanations.
"""
        return repair_prompt.strip()

    @classmethod
    async def repair_generation(
        cls,
        adapter: BaseModelAdapter,
        request: GenerationRequest,
        initial_response: GenerationResponse,
        initial_validation: ValidationResult,
        schema_path_or_dict: Any,
        max_repair_attempts: int = 2
    ) -> Tuple[GenerationResponse, ValidationResult]:
        """Execute bounded repair loop until schema validation passes or max attempts are reached."""
        current_response = initial_response
        current_validation = initial_validation
        repair_count = 0
        total_latency = initial_response.latency_ms
        total_input_tokens = initial_response.input_tokens
        total_output_tokens = initial_response.output_tokens

        while not current_validation.is_valid and repair_count < max_repair_attempts:
            repair_count += 1

            # Build targeted repair prompt
            repair_prompt = cls.build_repair_prompt(
                original_prompt=request.prompt,
                failed_output=current_response.text,
                errors=current_validation.errors,
                schema=schema_path_or_dict if isinstance(schema_path_or_dict, dict) else None
            )

            # Metadata with repair state
            repair_metadata = dict(request.metadata)
            repair_metadata["is_repair"] = True
            repair_metadata["repair_attempt"] = repair_count

            repair_request = GenerationRequest(
                task_type=request.task_type,
                prompt=repair_prompt,
                variables=request.variables,
                model=request.model,
                temperature=0.0,  # Zero temperature for deterministic repair
                max_tokens=request.max_tokens,
                response_format="json",
                timeout=request.timeout,
                metadata=repair_metadata
            )

            try:
                repair_resp = await adapter.generate(repair_request)
                total_latency += repair_resp.latency_ms
                total_input_tokens += repair_resp.input_tokens
                total_output_tokens += repair_resp.output_tokens
                current_response = repair_resp

                # Attempt JSON extraction
                parsed_json, _ = JSONParser.extract_and_parse(repair_resp.text)
                # Schema validation
                current_validation = SchemaValidator.validate(
                    data=parsed_json,
                    schema_path_or_dict=schema_path_or_dict,
                    task_type=request.task_type
                )

                if current_validation.is_valid:
                    # Successfully repaired!
                    current_response.status = "REPAIRED"
                    current_response.structured_output = current_validation.data
                    current_response.repair_count = repair_count
                    current_response.latency_ms = round(total_latency, 2)
                    current_response.input_tokens = total_input_tokens
                    current_response.output_tokens = total_output_tokens
                    return current_response, current_validation

            except (JSONParseError, Exception) as exc:
                current_validation = ValidationResult(
                    is_valid=False,
                    errors=[f"Repair attempt {repair_count} failed: {str(exc)}"],
                    error_type="JSON_PARSE_ERROR" if isinstance(exc, JSONParseError) else "UNKNOWN_ERROR"
                )

        # Max repair attempts exhausted without success
        current_response.status = "FAILED"
        current_response.repair_count = repair_count
        current_response.latency_ms = round(total_latency, 2)
        current_response.input_tokens = total_input_tokens
        current_response.output_tokens = total_output_tokens
        current_response.error = f"Exhausted {max_repair_attempts} repair attempts. Last errors: {'; '.join(current_validation.errors)}"
        return current_response, current_validation
