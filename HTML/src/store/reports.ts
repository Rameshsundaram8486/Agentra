/* Performance figures and the report catalogue (S10). Every figure is computed from the demo records; where the
   records cannot support a figure (cost and utilization over time), the report says it is a placeholder. */
import type { Agent, Decision, World } from "@/types";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { PHASES } from "@/data/lifecycle";
import { QA } from "@/data/seed/phaseContent";
import { secondsBetween } from "@/data/time";
import { briefing } from "./briefing";
import { bottlenecks, executionSeconds, queues, successRate } from "./operations";
import { agentType, byId, completion, currentPhase, isOpenDecision, kpis, nextMilestone, projectHealth, riskLevel, riskScore } from "./selectors";

/* Figures --------------------------------------------------------------------------------------------- */

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

/** Hours from when a decision was raised to when a person settled it. */
export function turnaroundHours(decision: Decision): number | null {
  return decision.outcome ? Math.round((secondsBetween(decision.createdAt, decision.outcome.at) / 3600) * 10) / 10 : null;
}

export function approvalTurnaround(world: World) {
  const decided = world.decisions.filter((d) => d.outcome).map((d) => ({ decision: d, hours: turnaroundHours(d)! }));
  const open = world.decisions.filter(isOpenDecision).map((d) => ({ decision: d, hours: Math.round(secondsBetween(d.createdAt, world.now) / 360) / 10 }));
  return { decided, open, median: median(decided.map((d) => d.hours)), oldestOpen: Math.max(0, ...open.map((o) => o.hours)) };
}

export interface AgentRow {
  agent: Agent;
  category: string;
  runs: number;
  succeeded: number;
  failed: number;
  successRate: number;
  avgSeconds: number;
  recordedCost: number; // simulated cost of the runs recorded in the demo
  tokens: number;
}

export function agentRows(world: World): AgentRow[] {
  return world.agents.map((agent) => {
    const runs = world.executions.filter((e) => e.agentId === agent.id);
    return {
      agent,
      category: CATEGORY_LABELS[agentType(world, agent.typeKey)?.category ?? "governance"].replace(" agents", ""),
      runs: agent.runs,
      succeeded: agent.succeeded,
      failed: agent.failed,
      successRate: successRate(agent),
      avgSeconds: agent.avgSeconds,
      recordedCost: Math.round(runs.reduce((s, e) => s + e.costUsd, 0) * 100) / 100,
      tokens: runs.reduce((s, e) => s + e.tokensIn + e.tokensOut, 0),
    };
  });
}

export function workforceTotals(world: World) {
  const runs = world.agents.reduce((s, a) => s + a.runs, 0);
  const succeeded = world.agents.reduce((s, a) => s + a.succeeded, 0);
  const failed = world.agents.reduce((s, a) => s + a.failed, 0);
  const avg = Math.round(world.agents.reduce((s, a) => s + a.avgSeconds * a.runs, 0) / Math.max(1, runs));
  const cost = Math.round(world.executions.reduce((s, e) => s + e.costUsd, 0) * 100) / 100;
  return { runs, succeeded, failed, successRate: Math.round((succeeded / Math.max(1, succeeded + failed)) * 1000) / 10, avgSeconds: avg, recordedCost: cost, recordedRuns: world.executions.length };
}

export function qaMetrics() {
  const rows = Object.entries(QA).flatMap(([projectId, qa]) => qa.suites.map((s) => ({ projectId, ...s })));
  const cases = rows.reduce((s, r) => s + r.cases, 0);
  const passed = rows.reduce((s, r) => s + r.passed, 0);
  const executed = rows.reduce((s, r) => s + r.passed + r.failed, 0);
  const defects = Object.entries(QA).flatMap(([projectId, qa]) => qa.defects.map((d) => ({ projectId, ...d })));
  return { rows, cases, passed, executed, passRate: Math.round((passed / Math.max(1, executed)) * 1000) / 10, defects };
}

/** Each project's progress against its budget and its milestones. */
export function projectPerformance(world: World) {
  return world.projects.map((project) => {
    const done = project.milestones.filter((m) => m.done).length;
    return {
      project,
      completion: completion(project),
      budgetUsed: Math.round((project.spentAed / project.budgetAed) * 100),
      milestones: `${done} of ${project.milestones.length}`,
      health: projectHealth(world, project).health,
      phase: currentPhase(project).phase,
      next: nextMilestone(project),
    };
  });
}

/* Reports --------------------------------------------------------------------------------------------- */

export type Cell = string | number;

export interface ReportSection {
  heading: string;
  text?: string;
  table?: { columns: string[]; rows: Cell[][] };
}

export interface ReportBody {
  summary: string;
  figures: { label: string; value: string }[];
  sections: ReportSection[];
  placeholder?: string;
}

export interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  audience: string;
  projectFilter: boolean; // whether the project filter applies
  build: (world: World, projectId: string) => ReportBody;
}

const inProject = (projectId: string) => (item: { projectId?: string }) => projectId === "all" || item.projectId === projectId;
const pct = (n: number) => `${n}%`;
const name = (world: World, projectId: string) => (projectId === "all" ? "all projects" : byId(world.projects, projectId)?.name ?? projectId);

export const REPORTS: ReportDefinition[] = [
  {
    id: "executive", title: "Executive company report", description: "Company health, projects, decisions waiting and the Project Owner Agent's priorities.", audience: "Owner", projectFilter: false,
    build: (world) => {
      const k = kpis(world);
      const brief = briefing(world);
      return {
        summary: brief.headline,
        figures: [
          { label: "Health score", value: `${brief.score} of 100` }, { label: "Active projects", value: String(k.activeProjects) },
          { label: "Projects at risk", value: String(k.projectsAtRisk) }, { label: "Decisions waiting", value: `${k.pendingDecisions} (${k.overdueDecisions} overdue)` },
        ],
        sections: [
          { heading: "Projects", table: { columns: ["Project", "Phase", "Health", "Completion"], rows: world.projects.map((p) => [p.name, `${currentPhase(p).phase}`, projectHealth(world, p).health.replace("_", " "), pct(completion(p))]) } },
          { heading: "Priorities recommended by the Project Owner Agent (proposals for people to decide)", table: { columns: ["#", "Priority"], rows: brief.priorities.map((p) => [p.rank, p.text]) } },
          { heading: "Top risks", table: { columns: ["Risk", "Title", "Score", "Status"], rows: brief.risks.map((r) => [r.code, r.title, riskScore(r), r.status]) } },
        ],
      };
    },
  },
  {
    id: "projects", title: "Project performance", description: "Completion, budget used, milestones and health for each project.", audience: "Owner, project managers", projectFilter: true,
    build: (world, projectId) => {
      const rows = projectPerformance(world).filter((r) => projectId === "all" || r.project.id === projectId);
      const overspend = rows.filter((r) => r.budgetUsed > r.completion + 10);
      return {
        summary: `${rows.length} project(s); ${overspend.length} spending faster than they progress.`,
        figures: [{ label: "Average completion", value: pct(Math.round(rows.reduce((s, r) => s + r.completion, 0) / Math.max(1, rows.length))) }, { label: "Spending ahead of progress", value: String(overspend.length) }],
        sections: [{ heading: "Projects", table: { columns: ["Project", "Phase", "Completion", "Budget used", "Milestones met", "Next milestone", "Health"], rows: rows.map((r) => [r.project.name, r.phase, pct(r.completion), pct(r.budgetUsed), r.milestones, r.next ? `${r.next.title} (${r.next.due.slice(0, 10)})` : "None", r.health.replace("_", " ")]) } }],
      };
    },
  },
  {
    id: "agents", title: "Agent performance", description: "Runs, success rate, run time and recorded cost for each agent.", audience: "Owner", projectFilter: false,
    build: (world) => {
      const t = workforceTotals(world);
      return {
        summary: `${t.runs} runs in total; ${t.successRate}% succeeded.`,
        figures: [{ label: "Runs", value: String(t.runs) }, { label: "Success rate", value: `${t.successRate}%` }, { label: "Failed runs", value: String(t.failed) }],
        sections: [{ heading: "Agents", table: { columns: ["Agent", "Category", "Runs", "Succeeded", "Failed", "Success rate", "Average run (s)"], rows: agentRows(world).sort((a, b) => b.runs - a.runs).map((r) => [r.agent.name, r.category, r.runs, r.succeeded, r.failed, `${r.successRate}%`, r.avgSeconds]) } }],
      };
    },
  },
  {
    id: "workflow", title: "Workflow efficiency", description: "Where work waits: queues, bottlenecks per phase and work waiting for people.", audience: "Project managers", projectFilter: true,
    build: (world, projectId) => {
      const q = queues(world);
      const f = inProject(projectId);
      return {
        summary: `${q.waitingOnPeople.filter(f).length} work item(s) waiting for people and ${q.ready.filter(f).length} ready to start in ${name(world, projectId)}.`,
        figures: [{ label: "Ready to start", value: String(q.ready.filter(f).length) }, { label: "Waiting on other work", value: String(q.waitingOnWork.filter(f).length) }, { label: "Waiting for people", value: String(q.waitingOnPeople.filter(f).length) }],
        sections: [
          { heading: "Bottlenecks in the MVP phases (all projects)", table: { columns: ["Phase", "Waiting for people", "Decisions open", "Blocked or failed"], rows: bottlenecks(world).map((b) => [`${b.phase} ${b.name}`, b.waitingTasks, b.pendingDecisions, b.blocked]) } },
          { heading: "Waiting for people", table: { columns: ["Work item", "Title", "State"], rows: q.waitingOnPeople.filter(f).map((t) => [t.key, t.title, t.state.replaceAll("_", " ")]) } },
        ],
      };
    },
  },
  {
    id: "phases", title: "Phase completion", description: "How many projects have passed each phase gate, and where they are now.", audience: "Owner", projectFilter: false,
    build: (world) => ({
      summary: `${world.projects.length} projects across 13 phases; the MVP covers Phases 7 to 11.`,
      figures: [{ label: "Gates passed", value: String(world.projects.reduce((s, p) => s + p.phases.filter((ph) => ph.state === "completed").length, 0)) }],
      sections: [{
        heading: "Phases", table: {
          columns: ["Phase", "Completed", "In this phase now", "MVP"],
          rows: PHASES.map((ph) => [`${ph.number} ${ph.name}`, world.projects.filter((p) => p.phases[ph.number - 1]!.state === "completed").length, world.projects.filter((p) => p.status !== "completed" && currentPhase(p).phase === ph.number).length, ph.mvp ? "Yes" : "Preview"]),
        },
      }],
    }),
  },
  {
    id: "qa", title: "QA quality metrics", description: "Test suites, pass rates and exit criteria from the QA phase.", audience: "Project managers, reviewers", projectFilter: false,
    build: () => {
      const m = qaMetrics();
      return {
        summary: `${m.passed} of ${m.executed} executed test cases passed (${m.passRate}%); ${m.cases - m.executed} blocked.`,
        figures: [{ label: "Pass rate", value: `${m.passRate}%` }, { label: "Test cases", value: String(m.cases) }, { label: "Blocked", value: String(m.cases - m.executed) }],
        sections: [{ heading: "Suites (Enterprise Intranet Modernization)", table: { columns: ["Suite", "Cases", "Passed", "Failed", "Blocked"], rows: m.rows.map((r) => [r.name, r.cases, r.passed, r.failed, r.blocked]) } }],
      };
    },
  },
  {
    id: "defects", title: "Defect trends", description: "Defects by severity and status.", audience: "Project managers", projectFilter: false,
    build: () => {
      const { defects } = qaMetrics();
      const open = defects.filter((d) => d.status === "open");
      return {
        summary: `${open.length} open defect(s), ${open.filter((d) => d.severity === "critical").length} critical.`,
        figures: (["critical", "major", "minor"] as const).map((s) => ({ label: s[0]!.toUpperCase() + s.slice(1), value: `${defects.filter((d) => d.severity === s).length} (${defects.filter((d) => d.severity === s && d.status === "open").length} open)` })),
        sections: [{ heading: "Defects", table: { columns: ["Defect", "Title", "Severity", "Status"], rows: defects.map((d) => [d.id, d.title, d.severity, d.status]) } }],
        placeholder: "The demo holds the current defect list only; a trend over time comes from defect history in Agentra.",
      };
    },
  },
  {
    id: "approvals", title: "Human approval turnaround", description: "How long decisions wait for people, decided and open.", audience: "Owner", projectFilter: true,
    build: (world, projectId) => {
      const t = approvalTurnaround(world);
      const decided = t.decided.filter((d) => inProject(projectId)(d.decision));
      const open = t.open.filter((o) => inProject(projectId)(o.decision));
      const m = median(decided.map((d) => d.hours));
      return {
        summary: `Median ${m === null ? "n/a" : `${m} h`} from raised to decided; ${open.length} open, the oldest ${Math.max(0, ...open.map((o) => o.hours))} h.`,
        figures: [{ label: "Median turnaround", value: m === null ? "n/a" : `${m} h` }, { label: "Decided", value: String(decided.length) }, { label: "Open", value: String(open.length) }],
        sections: [
          { heading: "Decided", table: { columns: ["Decision", "Title", "Outcome", "Hours"], rows: decided.map((d) => [d.decision.code, d.decision.title, d.decision.status, d.hours]) } },
          { heading: "Open", table: { columns: ["Decision", "Title", "Waiting (h)", "Decides"], rows: open.map((o) => [o.decision.code, o.decision.title, o.hours, o.decision.allowedRoles.join(" or ")]) } },
        ],
      };
    },
  },
  {
    id: "risks", title: "Project risk analysis", description: "The risk register by score and category, with incidents.", audience: "Owner, project managers", projectFilter: true,
    build: (world, projectId) => {
      const risks = world.risks.filter(inProject(projectId)).sort((a, b) => riskScore(b) - riskScore(a));
      const open = risks.filter((r) => r.status !== "closed");
      return {
        summary: `${open.length} open risk(s) in ${name(world, projectId)}, ${open.filter((r) => riskScore(r) >= 12).length} high or critical.`,
        figures: [{ label: "Open", value: String(open.length) }, { label: "High or critical", value: String(open.filter((r) => riskScore(r) >= 12).length) }],
        sections: [
          { heading: "Risks", table: { columns: ["Risk", "Title", "Category", "Score", "Level", "Status", "Mitigation"], rows: risks.map((r) => [r.code, r.title, r.category, riskScore(r), riskLevel(r), r.status, r.mitigation]) } },
          { heading: "Incidents", table: { columns: ["Incident", "Title", "Severity", "Status"], rows: world.incidents.filter(inProject(projectId)).map((i) => [i.code, i.title, i.severity, i.status]) } },
        ],
      };
    },
  },
  {
    id: "cost", title: "Cost and utilization", description: "Model cost of recorded runs, agent utilization and project budgets.", audience: "Owner", projectFilter: false,
    build: (world) => {
      const t = workforceTotals(world);
      const working = world.agents.filter((a) => a.status === "working").length;
      const runSeconds = world.executions.reduce((s, e) => s + executionSeconds(e, world.now), 0);
      return {
        summary: `Recorded runs cost $${t.recordedCost.toFixed(2)} (simulated); ${working} of ${world.agents.length} agents working now.`,
        figures: [{ label: "Recorded model cost", value: `$${t.recordedCost.toFixed(2)}` }, { label: "Agents working", value: `${working} of ${world.agents.length}` }, { label: "Recorded run time", value: `${Math.round(runSeconds / 60)} min` }],
        sections: [{ heading: "Project budgets", table: { columns: ["Project", "Budget (AED)", "Spent (AED)", "Used"], rows: world.projects.map((p) => [p.name, p.budgetAed, p.spentAed, pct(Math.round((p.spentAed / p.budgetAed) * 100))]) } }],
        placeholder: "Placeholder: monthly cost and utilization come from the model gateway's usage records in Agentra (monthly cap USD 50). These figures cover only the runs recorded in this demo.",
      };
    },
  },
];

/** A report as CSV: one block per table, headed by its section. */
export function reportCsv(title: string, body: ReportBody): string {
  const cell = (c: Cell) => {
    const text = String(c);
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  const lines = [cell(title), cell(body.summary), ""];
  for (const f of body.figures) lines.push([cell(f.label), cell(f.value)].join(","));
  for (const section of body.sections.filter((s) => s.table)) {
    lines.push("", cell(section.heading), section.table!.columns.map(cell).join(","));
    for (const row of section.table!.rows) lines.push(row.map(cell).join(","));
  }
  return lines.join("\r\n");
}
