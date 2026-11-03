"""Only this project's artifacts, of the types the task accepts, enter a task's context."""

import uuid
from collections.abc import Collection

from app.modules.artifacts.schemas import VersionRecord


def input_problems(record: VersionRecord, project_id: uuid.UUID, allowed_types: Collection[str]) -> list[str]:
    problems = []
    if record.project_id != project_id:
        problems.append("The document belongs to another project")
    if record.artifact_type not in allowed_types:
        problems.append(f"This task reads {', '.join(sorted(allowed_types))} documents, not {record.artifact_type}")
    return problems
