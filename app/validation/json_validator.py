"""JSON Schema and Pydantic validation subsystem for structured outputs."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonschema
from pydantic import BaseModel, Field, ValidationError


class SchemaValidationError(Exception):
    """Raised when JSON payload violates schema specification."""
    def __init__(self, message: str, errors: List[str], error_type: str = "SCHEMA_VIOLATION"):
        super().__init__(message)
        self.errors = errors
        self.error_type = error_type


class ValidationResult(BaseModel):
    """Detailed outcome of schema validation check."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    error_type: Optional[str] = None
    data: Optional[Any] = None


class EventBriefModel(BaseModel):
    """Pydantic model representation of EventBrief."""
    event_name: str = Field(..., min_length=2)
    date: str = Field(..., min_length=2)
    location: str = Field(..., min_length=2)
    description: str = Field(..., min_length=5)


class ContentPackModel(BaseModel):
    """Pydantic model representation of ContentPack."""
    headline: str = Field(..., min_length=5)
    summary: str = Field(..., min_length=10)
    key_points: List[str] = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=3)


TASK_PYDANTIC_MODELS: Dict[str, Any] = {
    "event_brief": EventBriefModel,
    "content_pack": ContentPackModel
}


class SchemaValidator:
    """Validates arbitrary structured data against JSON Schemas and Pydantic models."""

    _schema_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_schema(cls, schema_path: str) -> Dict[str, Any]:
        """Load and cache JSON Schema from filepath."""
        if schema_path in cls._schema_cache:
            return cls._schema_cache[schema_path]

        resolved_path = Path(schema_path)
        if not resolved_path.is_absolute():
            # Resolve relative to project root
            root_dir = Path(__file__).parent.parent.parent
            resolved_path = root_dir / schema_path

        if not resolved_path.exists():
            raise FileNotFoundError(f"Schema file not found at: {resolved_path}")

        with open(resolved_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        cls._schema_cache[schema_path] = schema
        return schema

    @classmethod
    def validate(cls, data: Any, schema_path_or_dict: Any, task_type: Optional[str] = None) -> ValidationResult:
        """Validate parsed data against JSON Schema and optional Pydantic model.

        Categorizes errors into MISSING_FIELD, WRONG_TYPE, EXTRA_FIELD, or SCHEMA_VIOLATION.
        """
        errors: List[str] = []
        error_type: Optional[str] = None

        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=[f"Expected JSON object (dictionary), received {type(data).__name__}"],
                error_type="WRONG_TYPE"
            )

        # 1. Pydantic validation if matching model exists
        if task_type and task_type in TASK_PYDANTIC_MODELS:
            model_cls = TASK_PYDANTIC_MODELS[task_type]
            try:
                model_instance = model_cls.model_validate(data)
                data = model_instance.model_dump()
            except ValidationError as pydantic_err:
                for err in pydantic_err.errors():
                    field_name = ".".join(str(loc) for loc in err["loc"])
                    msg = f"Field '{field_name}': {err['msg']}"
                    errors.append(msg)
                    err_kind = err.get("type", "")
                    if "missing" in err_kind:
                        error_type = "MISSING_FIELD"
                    elif "type" in err_kind:
                        error_type = "WRONG_TYPE"
                    else:
                        error_type = "SCHEMA_VIOLATION"

                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    error_type=error_type or "SCHEMA_VIOLATION",
                    data=data
                )

        # 2. JSON Schema validation
        schema: Optional[Dict[str, Any]] = None
        if isinstance(schema_path_or_dict, str):
            schema = cls.load_schema(schema_path_or_dict)
        elif isinstance(schema_path_or_dict, dict):
            schema = schema_path_or_dict

        if schema:
            validator = jsonschema.Draft7Validator(schema)
            for err in validator.iter_errors(data):
                field = ".".join(str(p) for p in err.path) if err.path else "root"
                errors.append(f"[{field}] {err.message}")

                if err.validator == "required":
                    error_type = "MISSING_FIELD"
                elif err.validator == "type":
                    error_type = "WRONG_TYPE"
                elif err.validator == "additionalProperties":
                    error_type = "EXTRA_FIELD"
                elif not error_type:
                    error_type = "SCHEMA_VIOLATION"

        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                error_type=error_type or "SCHEMA_VIOLATION",
                data=data
            )

        return ValidationResult(is_valid=True, errors=[], data=data)
