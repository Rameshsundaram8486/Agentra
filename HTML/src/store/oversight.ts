/* What the Project Owner Agent watches, derived from the records: each project's health assessment, failed runs,
   stuck work, overdue decisions, delays and the governance checks behind Risk and Compliance. These are facts read
   from records; the agent's proposals live in briefing.ts and are labelled as proposals. */
import type { Execution, Incident, Milestone, Project, Task, World } from "@/types";
import { secondsBetween } from "@/data/time";
import { decisionsFor, gatingDecision } from "./operations";
import { completion, isOpenDecision, isOverdue, OPEN_INCIDENT, projectHealth, riskScore } from "./selectors";

/* Health assessment ----------------------------------------------------------------------------------- */

export interface HealthSignal {
  label: string;
  count: number;
  tone: "danger" | "warning" | "neutral";
  detail: string[];
  link: string;
}

/** The signals behind one project's health, with the records each comes from. */
export function healthSignals(world: World, project: Project): HealthSignal[] {
  const risks = world.risks.filter((r) => r.projectId === project.id && r.status !== "closed" && riskScore(r) >= 12);
  const incidents = world.incidents.filter((i) => i.projectId === project.id && (OPEN_INCIDENT as readonly string[]).includes(i.status));
  const stuckTasks = world.tasks.filter((t) => t.projectId === project.id && (t.state === "failed" || t.state === "blocked"));
  const overdue = world.decisions.filter((d) => d.projectId === project.id && isOverdue(d, world.now));
  const late = lateMilestones(world, project);
  const waiting = world.decisions.filter((d) => d.projectId === project.id && isOpenDecision(d) && !isOverdue(d, world.now));
  return [
    { label: "High or critical risks", count: risks.length, tone: risks.some((r) => riskScore(r) >= 16) ? "danger" : "warning", detail: risks.map((r) => `${r.code}: ${r.title} (score ${riskScore(r)})`), link: "/risk" },
    { label: "Open incidents", count: incidents.length, tone: "warning", detail: incidents.map((i) => `${i.code}: ${i.title}`), link: `/owner?incident=${incidents[0]?.id ?? ""}` },
    { label: "Failed or blocked work", count: stuckTasks.length, tone: "warning", detail: stuckTasks.map((t) => `${t.key} ${t.state}: ${t.title}`), link: `/projects/${project.id}?tab=tasks` },
    { label: "Overdue decisions", count: overdue.length, tone: overdue.some((d) => d.priority === "critical") ? "danger" : "warning", detail: overdue.map((d) => `${d.code}: ${d.title}`), link: "/decisions" },
    { label: "Late milestones", count: late.length, tone: "warning", detail: late.map((m) => `${m.title}, due ${m.due.slice(0, 10)}`), link: "/milestones" },
    { label: "Decisions waiting (in time)", count: waiting.length, tone: "neutral", detail: waiting.map((d) => `${d.code}: ${d.title}`), link: "/decisions" },
  ];
}

/** Budget used against work done: a project spending faster than it progresses. */
export function burn(project: Project): { spent: number; done: number; ahead: boolean } {
  const spent = Math.round((project.spentAed / project.budgetAed) * 100);
  const done = completion(project);
  return { spent, done, ahead: spent > done + 10 };
}

/* Delays and stuck work ------------------------------------------------------------------------------- */

export function lateMilestones(world: World, project: Project): Milestone[] {
  return project.milestones.filter((m) => !m.done && Date.parse(m.due) < Date.parse(world.now));
}

export interface Delay {
  project: Project;
  milestone: Milestone;
  kind: "late" | "at_risk";
  reason: string;
}

/** Milestones already late, and milestones due within 7 days on a project that is at risk or critical. */
export function delays(world: World): Delay[] {
  const out: Delay[] = [];
  for (const project of world.projects.filter((p) => p.status === "active")) {
    const health = projectHealth(world, project);
    for (const milestone of project.milestones.filter((m) => !m.done)) {
      const days = secondsBetween(world.now, milestone.due) / 86_400;
      if (days < 0) out.push({ project, milestone, kind: "late", reason: `Due ${Math.round(-days)} day(s) ago` });
      else if (days <= 7 && (health.health === "critical" || health.health === "at_risk")) out.push({ project, milestone, kind: "at_risk", reason: health.reasons[0] ?? "Project at risk" });
    }
  }
  return out;
}

export interface StuckItem {
  task: Task;
  reason: string;
  hours: number;
  link: string;
}

const STUCK_HOURS = 24;

/** Work that is not moving: failed or blocked tasks, and tasks waiting for people for more than a day. */
export function stuckWork(world: World): StuckItem[] {
  const items: StuckItem[] = [];
  for (const task of world.tasks) {
    if (task.state === "failed" || task.state === "blocked") {
      items.push({ task, reason: task.state === "failed" ? "Its last run failed" : "Blocked", hours: hoursSince(world, task.startedAt ?? task.createdAt), link: `/projects/${task.projectId}?tab=tasks` });
      continue;
    }
    const waitingOnPeople = task.state === "waiting_for_review" || task.state === "waiting_for_input" || (task.state === "not_started" && gatingDecision(world, task));
    if (!waitingOnPeople) continue;
    const decisions = decisionsFor(world, task);
    const since = decisions.map((d) => d.createdAt).sort()[0];
    if (!since) continue;
    const hours = hoursSince(world, since);
    if (hours >= STUCK_HOURS) items.push({ task, reason: `Waiting for ${decisions.map((d) => d.code).join(", ")}`, hours, link: `/decisions?id=${decisions[0]!.id}` });
  }
  return items.sort((a, b) => b.hours - a.hours);
}

function hoursSince(world: World, iso: string): number {
  return Math.max(0, Math.round(secondsBetween(iso, world.now) / 3600));
}

/** Failed runs, newest first, with the incident opened for each, if any. */
export function failedRuns(world: World): { execution: Execution; incident?: Incident }[] {
  return world.executions
    .filter((e) => e.status === "failed")
    .sort((a, b) => Date.parse(b.endedAt ?? b.startedAt) - Date.parse(a.endedAt ?? a.startedAt))
    .map((execution) => ({ execution, incident: world.incidents.find((i) => i.executionId === execution.id) }));
}

/* Governance checks ----------------------------------------------------------------------------------- */

export interface ComplianceCheck {
  id: string;
  title: string;
  passed: boolean;
  detail: string;
  link: string;
}

/** The rules Agentra enforces, checked against the records as they are now. */
export function complianceChecks(world: World): ComplianceCheck[] {
  const settled = world.decisions.filter((d) => d.outcome);
  const approvedApprovals = world.decisions.filter((d) => d.kind === "approval" && (d.status === "approved" || d.status === "modified"));
  const unbound = approvedApprovals.filter((d) => d.artifactId && !d.outcome?.boundTo);
  const byAgents = settled.filter((d) => !world.people.some((p) => p.id === d.outcome!.by));
  const wrongRole = settled.filter((d) => {
    const person = world.people.find((p) => p.id === d.outcome!.by);
    return person && !d.allowedRoles.includes(person.role);
  });
  const overdue = world.decisions.filter((d) => isOverdue(d, world.now));
  const highRisks = world.risks.filter((r) => r.status !== "closed" && riskScore(r) >= 12);
  const unowned = highRisks.filter((r) => !r.ownerId || !r.mitigation);
  const unaudited = settled.filter((d) => !world.audit.some((a) => a.target === d.code && a.action === "decision.outcome"));
  const openIncidents = world.incidents.filter((i) => (OPEN_INCIDENT as readonly string[]).includes(i.status));
  const unconfirmedClosed = world.incidents.filter((i) => i.status === "closed" && !i.rca.verifiedBy);
  return [
    { id: "people-decide", title: "Every decision was made by a person, never an agent", passed: byAgents.length === 0, detail: byAgents.length ? byAgents.map((d) => d.code).join(", ") : `${settled.length} decisions, all by people`, link: "/decisions" },
    { id: "roles", title: "Every decision was made by a role allowed to make it", passed: wrongRole.length === 0, detail: wrongRole.length ? wrongRole.map((d) => d.code).join(", ") : "All within their roles", link: "/decisions" },
    { id: "bound", title: "Every approval is bound to the version it approved", passed: unbound.length === 0, detail: unbound.length ? unbound.map((d) => d.code).join(", ") : `${approvedApprovals.length} approval(s) checked`, link: "/approvals" },
    { id: "audited", title: "The audit trail records every human decision", passed: unaudited.length === 0, detail: unaudited.length ? `Missing: ${unaudited.map((d) => d.code).join(", ")}` : `${settled.length} of ${settled.length} recorded`, link: "/admin/settings" },
    { id: "deadlines", title: "No decision is past its deadline", passed: overdue.length === 0, detail: overdue.length ? overdue.map((d) => `${d.code} overdue`).join(", ") : "All in time", link: "/decisions" },
    { id: "risk-owners", title: "High risks have an owner and a mitigation", passed: unowned.length === 0, detail: `${highRisks.length} high or critical risk(s) open`, link: "/risk" },
    { id: "rca", title: "Open incidents have a root-cause analysis with a named owner", passed: openIncidents.every((i) => i.rca.ownerId && i.rca.correctiveAction), detail: `${openIncidents.length} open incident(s)`, link: "/owner" },
    { id: "verified", title: "Closed incidents were verified by a person", passed: unconfirmedClosed.length === 0, detail: unconfirmedClosed.length ? unconfirmedClosed.map((i) => i.code).join(", ") : "All verified", link: "/owner" },
  ];
}
