/* Rules every state of the demo world must satisfy, at the start and after every simulation step or human action.
   They are what keeps the screens from contradicting each other. */
import type { World } from "@/types";
import { byId, taskStarted } from "@/store/selectors";

export function invariantProblems(world: World): string[] {
  const problems: string[] = [];
  const ids = (items: { id: string }[]) => new Set(items.map((i) => i.id));
  const projects = ids(world.projects);
  const agents = ids(world.agents);
  const tasks = ids(world.tasks);
  const people = ids(world.people);

  for (const project of world.projects) {
    if (!world.customers.some((c) => c.id === project.customerId)) problems.push(`${project.id}: unknown customer`);
    if (!people.has(project.managerId)) problems.push(`${project.id}: unknown manager`);
    if (project.phases.length !== 13) problems.push(`${project.id}: has ${project.phases.length} phases`);
    const open = project.phases.filter((p) => p.state !== "completed" && p.state !== "upcoming");
    if (open.length > 1) problems.push(`${project.id}: ${open.length} phases in progress at once`);
    const firstOpen = project.phases.findIndex((p) => p.state !== "completed");
    if (firstOpen >= 0 && project.phases.slice(firstOpen + 1).some((p) => p.state === "completed")) problems.push(`${project.id}: a phase completed after an unfinished one`);
    if (project.status === "completed" && project.phases.some((p) => p.state !== "completed")) problems.push(`${project.id}: completed with open phases`);
  }

  for (const task of world.tasks) {
    if (!projects.has(task.projectId)) problems.push(`${task.id}: unknown project`);
    if (task.agentId && !agents.has(task.agentId)) problems.push(`${task.id}: unknown agent`);
    for (const dep of task.dependsOn) {
      if (!tasks.has(dep)) problems.push(`${task.id}: depends on unknown ${dep}`);
      else if (task.state === "completed" && byId(world.tasks, dep)!.state !== "completed") problems.push(`${task.id}: completed before its dependency ${dep}`);
      else if (task.state === "in_progress" && byId(world.tasks, dep)!.state !== "completed") problems.push(`${task.id}: in progress before its dependency ${dep}`);
    }
    if (taskStarted(task) && !task.startedAt) problems.push(`${task.id}: ${task.state} but never started`);
    if (task.state === "completed" && !task.completedAt) problems.push(`${task.id}: completed without a completion time`);
  }

  for (const agent of world.agents) {
    if (!world.agentTypes.some((t) => t.key === agent.typeKey)) problems.push(`${agent.id}: unknown type`);
    const task = byId(world.tasks, agent.taskId);
    if (agent.taskId && !task) problems.push(`${agent.id}: unknown task`);
    if (agent.status === "working" && task && task.state !== "in_progress") problems.push(`${agent.id}: working, but ${task.key} is ${task.state}`);
    if (agent.status === "waiting_approval" && (!task || !["waiting_for_review", "waiting_for_input"].includes(task.state))) {
      problems.push(`${agent.id}: waiting for approval without a task waiting for review or input`);
    }
    if (agent.succeeded + agent.failed > agent.runs) problems.push(`${agent.id}: more outcomes than runs`);
  }

  for (const execution of world.executions) {
    if (!agents.has(execution.agentId)) problems.push(`${execution.id}: unknown agent`);
    if (execution.projectId && !projects.has(execution.projectId)) problems.push(`${execution.id}: unknown project`);
    if (execution.taskId && !tasks.has(execution.taskId)) problems.push(`${execution.id}: unknown task`);
    const agent = byId(world.agents, execution.agentId);
    if ((execution.status === "running" || execution.status === "retrying") && agent?.status !== "working") problems.push(`${execution.id}: running, but ${agent?.id} is ${agent?.status}`);
    if ((execution.status === "succeeded" || execution.status === "failed") && !execution.endedAt) problems.push(`${execution.id}: finished without an end time`);
  }
  const running = world.executions.filter((e) => e.status === "running" || e.status === "retrying");
  for (const agent of world.agents) {
    if (running.filter((e) => e.agentId === agent.id).length > 1) problems.push(`${agent.id}: more than one running execution`);
  }

  for (const decision of world.decisions) {
    if (!projects.has(decision.projectId)) problems.push(`${decision.code}: unknown project`);
    if (!agents.has(decision.originAgentId)) problems.push(`${decision.code}: unknown agent`);
    if (decision.recommended && !decision.options.some((o) => o.key === decision.recommended)) problems.push(`${decision.code}: recommendation is not an option`);
    const decided = ["approved", "modified", "rejected", "deferred"].includes(decision.status);
    if (decided && !decision.outcome) problems.push(`${decision.code}: ${decision.status} without an outcome`);
    if (decision.outcome && !people.has(decision.outcome.by)) problems.push(`${decision.code}: decided by someone who is not a person`);
  }

  for (const risk of world.risks) if (!projects.has(risk.projectId)) problems.push(`${risk.code}: unknown project`);
  for (const incident of world.incidents) if (!projects.has(incident.projectId)) problems.push(`${incident.code}: unknown project`);
  for (const artifact of world.artifacts) {
    if (!projects.has(artifact.projectId)) problems.push(`${artifact.id}: unknown project`);
    const numbers = artifact.versions.map((v) => v.no);
    if (numbers.some((n, i) => i > 0 && n <= numbers[i - 1]!)) problems.push(`${artifact.id}: version numbers not increasing`);
  }
  return problems;
}
