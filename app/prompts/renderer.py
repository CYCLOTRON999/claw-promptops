"""Deterministic prompt template rendering with strict variable validation."""

import re
from typing import Any, Dict
from app.prompts.loader import PromptDefinition


class PromptVariableError(ValueError):
    """Raised when a required prompt template variable is missing or invalid."""
    pass


class PromptRenderer:
    """Renders prompt templates with strict variable validation and no silent defaults."""

    @staticmethod
    def render(prompt_def: PromptDefinition, variables: Dict[str, Any]) -> str:
        """Render a PromptDefinition against provided variables.

        Validates all required variables exist. Never silently inserts 'None'.
        """
        provided_vars = dict(variables)

        # Apply defaults for variables not provided
        for var_spec in prompt_def.variables:
            if var_spec.name not in provided_vars and var_spec.default is not None:
                provided_vars[var_spec.name] = var_spec.default

        # Check for missing required variables
        missing_vars = []
        for var_spec in prompt_def.variables:
            if var_spec.required:
                val = provided_vars.get(var_spec.name)
                if val is None or (isinstance(val, str) and not val.strip()):
                    missing_vars.append(var_spec.name)

        if missing_vars:
            raise PromptVariableError(
                f"Missing required variable(s) for prompt '{prompt_def.name}' (v{prompt_def.version}): "
                f"{', '.join(missing_vars)}"
            )

        rendered = prompt_def.template

        # Match all {{variable}} patterns
        pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name not in provided_vars:
                raise PromptVariableError(
                    f"Template referenced undeclared variable '{{{{{var_name}}}}}' "
                    f"in prompt '{prompt_def.name}' (v{prompt_def.version})"
                )
            val = provided_vars[var_name]
            if val is None:
                raise PromptVariableError(
                    f"Variable '{var_name}' evaluated to None in prompt '{prompt_def.name}' (v{prompt_def.version})"
                )
            return str(val)

        rendered = pattern.sub(replace_var, rendered)
        return rendered.strip()
