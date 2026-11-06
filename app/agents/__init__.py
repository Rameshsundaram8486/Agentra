"""Phase-specific agent logic. Declarative definitions live in config/agents/; this maps them to code."""

from app.agents.base import AgentTask


def task_implementation(agent_key: str, task_key: str) -> AgentTask | None:
    from app.agents.business_analyst.agent import ClarifyBrief
    from app.agents.business_analyst.draft import ApplyChangeRequest, DraftRequirements
    from app.agents.developer.agent import ReviewFeasibility
    from app.agents.developer.backlog import PlanBacklog
    from app.agents.security_reviewer.agent import ReviewSecurity
    from app.agents.solution_architect.agent import CompareOptions
    from app.agents.solution_architect.design import ApplyDesignChange, DraftDesign

    implementations = (
        ClarifyBrief(), DraftRequirements(), ApplyChangeRequest(), CompareOptions(), DraftDesign(), ReviewSecurity(), ReviewFeasibility(), PlanBacklog(),
        ApplyDesignChange(),
    )
    tasks: dict[tuple[str, str], AgentTask] = {(task.agent_key, task.task_key): task for task in implementations}  # type: ignore[misc]
    return tasks.get((agent_key, task_key))
