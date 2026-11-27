/* Derived values. Nothing here is stored: health, completion, KPIs and counts are computed from the records, so two
   screens can never disagree about them. */
import type { Agent, AgentType, Decision, Health, Person, Project, ProjectPhase, Risk, Task, World } from "@/types";

export const OPEN_INCIDENT = ["open", "investigating"] as const;
const TASK_STARTED = ["in_progress", "waiting_for_input", "waiting_for_review", "changes_requested", "blocked", "failed", "completed"];

/* Lookups ------------------------------------------------------------------------------------------- */

export function byId<T extends { id: string }>(items: T[], id: string | undefined): T | undefined {
  return id === undefined ? undefined : items.find((item) => item.id === id);
}

export function agentType(world: World, key: string): AgentType | undefined {
  return world.agentTypes.find((t) => t.key === key);
}

/** A person's or an agent's display name. */
export function actorName(world: World, id: string): string {
  if (id === "system") return "Agentra";
  return byId<Person>(world.people, id)?.name ?? byId<Agent>(world.agents, id)?.name ?? id;
}

/* Projects ------------------------------------------------------------------------------------------ */

export function currentPhase(project: Project): ProjectPhase {
  const open = project.phases.find((p) => p.state !== "completed" && p.state !== "upcoming");
  return open ?? project.phases.find((p) => p.state === "upcoming") ?? project.phases[project.phases.length - 1]!;
}

export function completion(project: Project): number {
  const total = project.phases.reduce((sum, p) => sum + (p.state === "completed" ? 100 : p.state === "upcoming" ? 0 : p.progress), 0);
  return Math.round(total / project.phases.length);
}

export function riskScore(risk: Risk): number {
  return risk.likelihood * risk.impact;
}

export function riskLevel(risk: Risk): "critical" | "high" | "medium" | "low" {
  const score = riskScore(risk);
  return score >= 16 ? "critical" : score >= 12 ? "high" : score >= 6 ? "medium" : "low";
}

export function isOverdue(decision: Decision, now: string): boolean {
  return isOpenDecision(decision) && Date.parse(decision.deadline) < Date.parse(now);
}

export function isOpenDecision(decision: Decision): boolean {
  return decision.status === "pending" || decision.status === "clarification_requested";
}

/** Health and the reasons for it, from the project's open risks, incidents, failed or blocked work and overdue decisions. */
export function projectHealth(world: World, project: Project): { health: Health; reasons: string[] } {
  if (project.status === "completed") return { health: "completed", reasons: ["All phases completed"] };
  if (project.status === "on_hold") return { health: "on_hold", reasons: [project.holdReason ?? "On hold"] };
  const critical: string[] = [];
  const atRisk: string[] = [];
  for (const risk of world.risks.filter((r) => r.projectId === project.id && r.status !== "closed")) {
    if (riskScore(risk) >= 16) critical.push(`${risk.code}: ${risk.title}`);
    else if (riskScore(risk) >= 12) atRisk.push(`${risk.code}: ${risk.title}`);
  }
  for (const decision of world.decisions.filter((d) => d.projectId === project.id && isOverdue(d, world.now))) {
    (decision.priority === "critical" ? critical : atRisk).push(`${decision.code} overdue: ${decision.title}`);
  }
  for (const incident of world.incidents.filter((i) => i.projectId === project.id && (OPEN_INCIDENT as readonly string[]).includes(i.status))) {
    atRisk.push(`${incident.code}: ${incident.title}`);
  }
  for (const task of world.tasks.filter((t) => t.projectId === project.id && (t.state === "failed" || t.state === "blocked"))) {
    atRisk.push(`${task.key} ${task.state}: ${task.title}`);
  }
  if (critical.length) return { health: "critical", reasons: [...critical, ...atRisk] };
  if (atRisk.length) return { health: "at_risk", reasons: atRisk };
  return { health: "on_track", reasons: ["No open high risks, failed work or overdue decisions"] };
}

export function projectAgents(world: World, projectId: string): Agent[] {
  const ids = new Set(world.tasks.filter((t) => t.projectId === projectId && t.agentId).map((t) => t.agentId!));
  for (const agent of world.agents) if (agent.projectId === projectId) ids.add(agent.id);
  return world.agents.filter((a) => ids.has(a.id));
}

export function nextMilestone(project: Project) {
  return project.milestones.filter((m) => !m.done).sort((a, b) => Date.parse(a.due) - Date.parse(b.due))[0];
}

/* Decisions and work -------------------------------------------------------------------------------- */

export function openDecisions(world: World, projectId?: string): Decision[] {
  return world.decisions
    .filter((d) => isOpenDecision(d) && (projectId === undefined || d.projectId === projectId))
    .sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority) || Date.parse(a.deadline) - Date.parse(b.deadline));
}

export function priorityRank(priority: Decision["priority"]): number {
  return { critical: 0, high: 1, medium: 2, low: 3 }[priority];
}

export function taskStarted(task: Task): boolean {
  return TASK_STARTED.includes(task.state);
}

export function latestVersion<T extends { versions: { no: number }[] }>(item: T): T["versions"][number] {
  return item.versions[item.versions.length - 1]!;
}

/* Company-wide ------------------------------------------------------------------------------------- */

export interface Kpis {
  activeProjects: number;
  activeAgents: number;
  tasksRunning: number;
  pendingDecisions: number;
  overdueDecisions: number;
  projectsAtRisk: number;
  completedDeliverables: number;
}

export function kpis(world: World): Kpis {
  const healths = world.projects.map((p) => projectHealth(world, p).health);
  return {
    activeProjects: world.projects.filter((p) => p.status === "active").length,
    activeAgents: world.agents.filter((a) => a.status === "working").length,
    tasksRunning: world.tasks.filter((t) => t.state === "in_progress").length,
    pendingDecisions: world.decisions.filter(isOpenDecision).length,
    overdueDecisions: world.decisions.filter((d) => isOverdue(d, world.now)).length,
    projectsAtRisk: healths.filter((h) => h === "at_risk" || h === "critical").length,
    completedDeliverables: world.artifacts.filter((a) => latestVersion(a).status === "approved").length,
  };
}

export function healthDistribution(world: World): Record<Health, number> {
  const counts: Record<Health, number> = { on_track: 0, at_risk: 0, critical: 0, on_hold: 0, completed: 0 };
  for (const project of world.projects) counts[projectHealth(world, project).health] += 1;
  return counts;
}

export function agentStatusCounts(world: World): Record<Agent["status"], number> {
  const counts: Record<Agent["status"], number> = { working: 0, idle: 0, waiting_approval: 0, blocked: 0, failed: 0, completed: 0 };
  for (const agent of world.agents) counts[agent.status] += 1;
  return counts;
}

export function unreadNotifications(world: World): number {
  return world.notifications.filter((n) => !n.read).length;
}
