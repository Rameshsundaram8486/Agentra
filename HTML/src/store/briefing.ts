/* The Project Owner Agent's briefing, derived from the records on every change. Findings are facts read from records;
   recommended actions and priorities are the agent's proposals for people to decide, and are labelled as such. */
import type { Decision, Risk, Role, World } from "@/types";
import { byId, isOverdue, OPEN_INCIDENT, openDecisions, priorityRank, projectHealth, riskScore } from "./selectors";

export type BriefingStatus = "healthy" | "watch" | "critical";

export interface Finding {
  severity: "critical" | "warning" | "info";
  text: string;
  link: string;
}

export interface Recommendation {
  text: string;
  basis: string; // the record it comes from
  owner: Role;
  link: string;
}

export interface Briefing {
  score: number; // 0-100
  status: BriefingStatus;
  headline: string;
  findings: Finding[];
  risks: Risk[];
  actions: Recommendation[];
  escalations: Decision[];
  priorities: { rank: number; text: string; link: string }[];
}

export function briefing(world: World): Briefing {
  const active = world.projects.filter((p) => p.status === "active");
  const health = active.map((p) => ({ project: p, ...projectHealth(world, p) }));
  const critical = health.filter((h) => h.health === "critical");
  const atRisk = health.filter((h) => h.health === "at_risk");
  const overdue = world.decisions.filter((d) => isOverdue(d, world.now));
  const incidents = world.incidents.filter((i) => (OPEN_INCIDENT as readonly string[]).includes(i.status));
  const failedRuns = world.executions.filter((e) => e.status === "failed" && Date.parse(world.now) - Date.parse(e.endedAt ?? e.startedAt) < 24 * 3600_000);
  const blocked = world.tasks.filter((t) => t.state === "blocked" || t.state === "failed");
  const waiting = openDecisions(world);

  const score = Math.max(0, Math.min(100, 100 - critical.length * 15 - atRisk.length * 8 - overdue.length * 6 - incidents.length * 4 - blocked.length * 2));
  const status: BriefingStatus = critical.length > 0 || score < 60 ? "critical" : atRisk.length > 0 || score < 80 ? "watch" : "healthy";
  const attention = critical.length + atRisk.length;
  const headline =
    attention === 0
      ? `All ${active.length} active projects are on track; ${waiting.length} decision${waiting.length === 1 ? "" : "s"} waiting for people.`
      : `${attention} of ${active.length} active projects need attention${overdue.length ? `; ${overdue.length} decision${overdue.length === 1 ? " is" : "s are"} overdue` : ""}.`;

  const findings: Finding[] = [
    ...critical.map((h) => ({ severity: "critical" as const, text: `${h.project.name} is critical: ${h.reasons[0]}`, link: `/projects/${h.project.id}` })),
    ...overdue.map((d) => ({ severity: "critical" as const, text: `${d.code} is overdue: ${d.title}`, link: `/decisions?id=${d.id}` })),
    ...atRisk.map((h) => ({ severity: "warning" as const, text: `${h.project.name} is at risk: ${h.reasons[0]}`, link: `/projects/${h.project.id}` })),
    ...incidents.map((i) => ({ severity: "warning" as const, text: `${i.code} ${i.status}: ${i.title}`, link: `/owner?incident=${i.id}` })),
    ...failedRuns.map((e) => ({ severity: "warning" as const, text: `Run failed in the last 24 h: ${e.title}`, link: `/operations?run=${e.id}` })),
    ...blocked.map((t) => ({ severity: "info" as const, text: `${t.key} is ${t.state}: ${t.title}`, link: `/projects/${t.projectId}` })),
  ];

  const risks = world.risks.filter((r) => r.status !== "closed").sort((a, b) => riskScore(b) - riskScore(a)).slice(0, 4);

  const actions: Recommendation[] = [
    ...overdue.map((d) => ({
      text: `Decide ${d.code}${d.recommended ? `; the ${byId(world.agents, d.originAgentId)?.name ?? "agent"} recommends "${d.options.find((o) => o.key === d.recommended)?.title}"` : ""}`,
      basis: `${d.code}, due ${d.deadline.slice(0, 10)}`,
      owner: d.allowedRoles[0]!,
      link: `/decisions?id=${d.id}`,
    })),
    ...incidents.map((i) => ({ text: i.rca.correctiveAction, basis: `${i.code} (hypothesis, ${i.rca.confidence} confidence)`, owner: "project_manager" as Role, link: `/owner?incident=${i.id}` })),
    ...waiting
      .filter((d) => !isOverdue(d, world.now) && (d.priority === "critical" || d.priority === "high") && !d.blockedBy)
      .slice(0, 3)
      .map((d) => ({ text: `Review ${d.code}: ${d.title}`, basis: `${d.priority} priority, waiting for ${d.allowedRoles.join(" or ")}`, owner: d.allowedRoles[0]!, link: `/decisions?id=${d.id}` })),
  ];

  const escalations = waiting.filter((d) => d.kind === "escalation");

  const ranked = [
    ...overdue.map((d) => ({ weight: 0, text: `Overdue: ${d.title} (${d.code})`, link: `/decisions?id=${d.id}` })),
    ...critical.map((h) => ({ weight: 1, text: `Bring ${h.project.name} back on track`, link: `/projects/${h.project.id}` })),
    ...waiting.filter((d) => !isOverdue(d, world.now) && !d.blockedBy).map((d) => ({ weight: 2 + priorityRank(d.priority), text: `${d.title} (${d.code})`, link: `/decisions?id=${d.id}` })),
    ...incidents.map((i) => ({ weight: 4, text: `Close out ${i.code}: ${i.title}`, link: `/owner?incident=${i.id}` })),
  ].sort((a, b) => a.weight - b.weight);
  const priorities = ranked.slice(0, 5).map((p, n) => ({ rank: n + 1, text: p.text, link: p.link }));

  return { score, status, headline, findings, risks, actions, escalations, priorities };
}
