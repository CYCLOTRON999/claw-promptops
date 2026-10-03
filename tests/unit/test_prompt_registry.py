"""Unit tests for PromptRegistry, PromptRenderer, and version immutability."""

import pytest
from app.prompts.loader import PromptDefinition, PromptVariable
from app.prompts.renderer import PromptRenderer, PromptVariableError
from app.prompts.registry import PromptRegistry, PromptRegistryError


def test_prompt_registry_loads_filesystem():
    registry = PromptRegistry()
    prompts = registry.list_prompts()
    assert "event_brief" in prompts
    assert "content_pack" in prompts

    versions = registry.list_versions("event_brief")
    assert "v1.0" in versions
    assert "v2.0" in versions


def test_prompt_registry_immutability():
    registry = PromptRegistry()
    existing_prompt = registry.get_prompt("event_brief", "v1.0")

    # Attempting to re-register the same version must fail
    duplicate = PromptDefinition(
        name="event_brief",
        version="v1.0",
        description="Tampered version",
        task_type="event_brief",
        template="Tampered"
    )
    with pytest.raises(PromptRegistryError, match="immutable and already registered"):
        registry.register(duplicate, allow_overwrite=False)


def test_prompt_renderer_success():
    registry = PromptRegistry()
    rendered = registry.render_prompt(
        name="event_brief",
        version="v1.0",
        variables={"instruction": "Plan a 3-day Delhi food walk trip"}
    )
    assert "Plan a 3-day Delhi food walk trip" in rendered
    assert "{{instruction}}" not in rendered


def test_prompt_renderer_missing_variable_raises():
    registry = PromptRegistry()
    with pytest.raises(PromptVariableError, match="Missing required variable"):
        registry.render_prompt(
            name="event_brief",
            version="v1.0",
            variables={}  # Empty variables
        )


def test_prompt_latest_version():
    registry = PromptRegistry()
    latest = registry.get_latest_prompt("event_brief")
    assert latest.version == "v2.0"
    assert "v2-hardened" in latest.metadata.get("tags", [])


def test_prompt_change_history():
    registry = PromptRegistry()
    history = registry.get_change_history("event_brief")
    assert len(history) >= 2
    versions = [h["version"] for h in history]
    assert "v1.0" in versions
    assert "v2.0" in versions
