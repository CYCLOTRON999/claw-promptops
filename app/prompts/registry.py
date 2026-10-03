"""Versioned immutable prompt registry for CLAW PromptOps."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from app.prompts.loader import PromptDefinition, discover_prompts
from app.prompts.renderer import PromptRenderer, PromptVariableError


class PromptRegistryError(Exception):
    """Raised when a prompt cannot be found or an immutable version is violated."""
    pass


class PromptRegistry:
    """Thread-safe registry for immutable, version-controlled prompts."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or (Path(__file__).parent.parent.parent / "prompts")
        # Structure: {prompt_name: {version_str: PromptDefinition}}
        self._registry: Dict[str, Dict[str, PromptDefinition]] = {}
        self.reload()

    def reload(self) -> None:
        """Scan directory and reload all prompt definitions."""
        self._registry.clear()
        prompts = discover_prompts(self.prompts_dir)
        for p in prompts:
            self.register(p, allow_overwrite=False)

    def register(self, prompt: PromptDefinition, allow_overwrite: bool = False) -> None:
        """Register a new prompt version. Rejects modifications to existing immutable versions."""
        name = prompt.name
        version = prompt.version

        if name not in self._registry:
            self._registry[name] = {}

        if not allow_overwrite and version in self._registry[name]:
            raise PromptRegistryError(
                f"Prompt version '{name}:{version}' is immutable and already registered. "
                "Increment the version (e.g. v1.1 or v2.0) instead of modifying in-place."
            )

        self._registry[name][version] = prompt

    def list_prompts(self) -> List[str]:
        """Return names of all registered prompt templates."""
        return sorted(list(self._registry.keys()))

    def list_versions(self, name: str) -> List[str]:
        """Return sorted list of all versions available for a prompt."""
        if name not in self._registry:
            raise PromptRegistryError(f"Prompt '{name}' is not registered.")
        return sorted(list(self._registry[name].keys()))

    def get_prompt(self, name: str, version: Optional[str] = None) -> PromptDefinition:
        """Retrieve a specific prompt version, or the latest version if version is None."""
        if name not in self._registry:
            raise PromptRegistryError(f"Prompt '{name}' does not exist in registry.")

        versions = self._registry[name]
        if not versions:
            raise PromptRegistryError(f"No versions found for prompt '{name}'.")

        if version is None or version == "latest":
            return self.get_latest_prompt(name)

        if version not in versions:
            available = ", ".join(versions.keys())
            raise PromptRegistryError(
                f"Version '{version}' not found for prompt '{name}'. Available versions: {available}"
            )

        return versions[version]

    def get_latest_prompt(self, name: str) -> PromptDefinition:
        """Retrieve the latest semantic version of a prompt."""
        if name not in self._registry:
            raise PromptRegistryError(f"Prompt '{name}' does not exist in registry.")

        versions = self._registry[name]
        latest_ver = sorted(list(versions.keys()))[-1]
        return versions[latest_ver]

    def render_prompt(self, name: str, version: Optional[str], variables: Dict[str, Any]) -> str:
        """Render the target prompt version with variable validation."""
        prompt_def = self.get_prompt(name, version)
        return PromptRenderer.render(prompt_def, variables)

    def get_change_history(self, name: str) -> List[Dict[str, Any]]:
        """Return chronological change history for a prompt."""
        if name not in self._registry:
            raise PromptRegistryError(f"Prompt '{name}' not found.")

        versions = self.list_versions(name)
        history = []
        for ver in versions:
            p = self._registry[name][ver]
            history.append({
                "version": ver,
                "date": p.creation_date,
                "description": p.description,
                "change_description": p.change_description,
                "variables": [v.model_dump() for v in p.variables],
                "task_type": p.task_type
            })
        return history


# Global singleton registry instance
default_prompt_registry = PromptRegistry()
