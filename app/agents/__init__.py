"""Phase-specific agent logic. Declarative definitions live in config/agents/; this maps them to code."""

from app.agents.base import AgentTask


def task_implementation(agent_key: str, task_key: str) -> AgentTask | None:
    from app.agents.business_analyst.agent import ClarifyBrief

    tasks: dict[tuple[str, str], AgentTask] = {(ClarifyBrief.agent_key, ClarifyBrief.task_key): ClarifyBrief()}
    return tasks.get((agent_key, task_key))
