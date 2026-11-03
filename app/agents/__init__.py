"""Phase-specific agent logic. Declarative definitions live in config/agents/; this maps them to code."""

from app.agents.base import AgentTask


def task_implementation(agent_key: str, task_key: str) -> AgentTask | None:
    from app.agents.business_analyst.agent import ClarifyBrief
    from app.agents.business_analyst.draft import DraftRequirements

    tasks: dict[tuple[str, str], AgentTask] = {
        (task.agent_key, task.task_key): task for task in (ClarifyBrief(), DraftRequirements())  # type: ignore[misc]
    }
    return tasks.get((agent_key, task_key))
