"""Structured output must parse as JSON and match the agent's versioned schema, including the size limits and
cross-field rules that are enforced in code rather than sent to the model."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.guardrails.findings import Finding

_MAX_ERRORS = 10


def _path(location: tuple[int | str, ...]) -> str:
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path or "(root)"


def parse_output[T: BaseModel](raw: str, model: type[T]) -> tuple[T | None, Any, list[Finding]]:
    """Returns (validated output or None, the parsed JSON or None, findings)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, None, [Finding("schema", "block", f"Output is not valid JSON: {exc.msg} at character {exc.pos}")]
    try:
        return model.model_validate(data), data, []
    except ValidationError as exc:
        findings = [
            Finding("schema", "block", error["msg"], _path(tuple(error["loc"])))
            for error in exc.errors(include_url=False)[:_MAX_ERRORS]
        ]
        if exc.error_count() > _MAX_ERRORS:
            findings.append(Finding("schema", "block", f"... and {exc.error_count() - _MAX_ERRORS} more schema errors"))
        return None, data, findings
