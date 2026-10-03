"""Prompt definition schema and YAML loader for versioned prompts."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class PromptVariable(BaseModel):
    """Specification of an expected template variable."""
    name: str
    description: str = ""
    required: bool = True
    default: Optional[Any] = None


class PromptModelRequirements(BaseModel):
    """Target model parameters configured for this prompt."""
    temperature: float = 0.0
    max_tokens: Optional[int] = 1024
    response_format: str = "json"


class PromptDefinition(BaseModel):
    """Immutable prompt version representation."""
    name: str
    version: str
    description: str
    task_type: str
    output_schema: Optional[str] = None
    variables: List[PromptVariable] = Field(default_factory=list)
    model_requirements: PromptModelRequirements = Field(default_factory=PromptModelRequirements)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    creation_date: str = ""
    change_description: str = ""
    template: str

    def get_variable_names(self) -> List[str]:
        return [v.name for v in self.variables]

    def get_required_variables(self) -> List[str]:
        return [v.name for v in self.variables if v.required and v.default is None]


def load_prompt_from_yaml(file_path: Path) -> PromptDefinition:
    """Read and validate a prompt YAML file into a PromptDefinition."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PromptDefinition(**data)


def discover_prompts(prompts_dir: Path) -> List[PromptDefinition]:
    """Scan prompts directory recursively for YAML files and load all versions."""
    definitions: List[PromptDefinition] = []
    if not prompts_dir.exists():
        return definitions

    for yaml_path in prompts_dir.rglob("*.yaml"):
        try:
            definition = load_prompt_from_yaml(yaml_path)
            definitions.append(definition)
        except Exception as exc:
            # Skip invalid YAML or malformed file during discovery
            continue

    return definitions
