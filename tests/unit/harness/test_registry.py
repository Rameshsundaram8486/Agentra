from pathlib import Path
from typing import Any

import pytest

from app.agents import task_implementation
from app.composition import CONFIG_DIR, load_policies
from app.harness.registry import AgentDefinitionError, load_registry

REGISTRY = load_registry(CONFIG_DIR / "agents")


def test_only_defined_agents_are_loaded_and_scaffolds_are_skipped() -> None:
    assert set(REGISTRY.agents) == {"business_analyst"}
    assert {task for _, task in REGISTRY.tasks} == {"clarify_brief", "draft_requirements", "apply_change_request"}
    task = REGISTRY.task("business_analyst", "clarify_brief")
    assert task is not None
    assert task.spec.input_artifact_types == ("project_brief",)
    assert task.prompt.version.startswith("clarify_brief.v1@")
    assert "$comment" not in task.schema_file.schema


def test_every_configured_task_has_code_and_policies_cross_check() -> None:
    for agent_key, task_key in REGISTRY.tasks:
        assert task_implementation(agent_key, task_key) is not None, f"{agent_key}.{task_key} has no implementation"
    load_policies()  # raises if a task names an unknown artifact type, phase or phase state


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].split("/")[-1]]
    if "anyOf" in schema:  # nullable: compare the non-null branch
        schema = next(branch for branch in schema["anyOf"] if branch.get("type") != "null")
        return _resolve(schema, root)
    return schema


def _shape(schema: dict[str, Any], root: dict[str, Any]) -> Any:
    """Property names, required names and nesting; ignores descriptions and limits."""
    schema = _resolve(schema, root)
    if schema.get("type") == "object":
        return {
            "required": sorted(schema.get("required", [])),
            "properties": {name: _shape(prop, root) for name, prop in sorted(schema["properties"].items())},
        }
    if schema.get("type") == "array":
        return ["array", _shape(schema["items"], root)]
    if "enum" in schema:
        return ["enum", sorted(schema["enum"])]
    return schema.get("type")


@pytest.mark.parametrize("key", sorted(REGISTRY.tasks), ids=lambda key: key[1])
def test_schema_sent_to_the_model_matches_the_schema_enforced_in_code(key: tuple[str, str]) -> None:
    sent = REGISTRY.tasks[key].schema_file.schema
    enforced = task_implementation(*key).output_model.model_json_schema()  # type: ignore[union-attr]

    assert _shape(sent, sent) == _shape(enforced, enforced)


def test_invalid_definitions_fail_startup(tmp_path: Path) -> None:
    agent_dir = tmp_path / "business_analyst"
    agent_dir.mkdir()
    source = (CONFIG_DIR / "agents" / "business_analyst" / "agent.yaml").read_text(encoding="utf-8")

    (agent_dir / "agent.yaml").write_text(source, encoding="utf-8")
    with pytest.raises(AgentDefinitionError, match="clarify_brief"):
        load_registry(tmp_path)  # prompt and schema files are missing

    (agent_dir / "agent.yaml").write_text(source.replace("autonomy: supervised", "autonomy: autonomous"), encoding="utf-8")
    with pytest.raises(AgentDefinitionError, match="autonomy"):
        load_registry(tmp_path)
