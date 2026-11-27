/* Chart data, derived from the records (nothing invented for a chart). */
import type { AgentCategory, World } from "@/types";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { agentType, currentPhase, projectHealth, riskScore } from "./selectors";

const DAY = 86_400_000;

function dayKey(time: number): string {
  // Days in UAE time (UTC+4).
  return new Date(time + 4 * 3600_000).toISOString().slice(0, 10);
}

/** Tasks completed and created per day over the last `days` days, with the running total of completed tasks. */
export function taskTrend(world: World, days = 14): { day: string; label: string; completed: number; created: number; total: number }[] {
  const end = Date.parse(world.now);
  const keys = Array.from({ length: days }, (_, i) => dayKey(end - (days - 1 - i) * DAY));
  const completedBefore = world.tasks.filter((t) => t.completedAt && dayKey(Date.parse(t.completedAt)) < keys[0]!).length;
  let total = completedBefore;
  return keys.map((key) => {
    const completed = world.tasks.filter((t) => t.completedAt && dayKey(Date.parse(t.completedAt)) === key).length;
    const created = world.tasks.filter((t) => dayKey(Date.parse(t.createdAt)) === key).length;
    total += completed;
    const date = new Date(`${key}T00:00:00Z`);
    return { day: key, label: date.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }), completed, created, total };
  });
}

/** Agent runs by category: succeeded and failed, from each agent's recorded run statistics. */
export function agentActivity(world: World): { category: string; succeeded: number; failed: number; running: number }[] {
  const rows = new Map<AgentCategory, { succeeded: number; failed: number; running: number }>();
  for (const agent of world.agents) {
    const category = agentType(world, agent.typeKey)?.category;
    if (!category) continue;
    const row = rows.get(category) ?? { succeeded: 0, failed: 0, running: 0 };
    row.succeeded += agent.succeeded;
    row.failed += agent.failed;
    row.running += world.executions.filter((e) => e.agentId === agent.id && (e.status === "running" || e.status === "retrying")).length;
    rows.set(category, row);
  }
  return [...rows.entries()].map(([category, row]) => ({ category: CATEGORY_LABELS[category].replace(" agents", ""), ...row })).sort((a, b) => b.succeeded - a.succeeded);
}

/** Open risks on a 5x5 likelihood-impact grid. */
export function riskMatrix(world: World): { likelihood: number; impact: number; codes: string[] }[] {
  const cells: { likelihood: number; impact: number; codes: string[] }[] = [];
  for (let likelihood = 5; likelihood >= 1; likelihood--) {
    for (let impact = 1; impact <= 5; impact++) {
      cells.push({ likelihood, impact, codes: world.risks.filter((r) => r.status !== "closed" && r.likelihood === likelihood && r.impact === impact).map((r) => r.code) });
    }
  }
  return cells;
}

export function riskByCategory(world: World): { category: string; open: number; score: number }[] {
  const open = world.risks.filter((r) => r.status !== "closed");
  const categories = [...new Set(open.map((r) => r.category))];
  return categories.map((category) => ({ category, open: open.filter((r) => r.category === category).length, score: Math.max(...open.filter((r) => r.category === category).map(riskScore)) }));
}

/** Where each project is in the lifecycle. */
export function lifecyclePositions(world: World) {
  return world.projects.map((p) => ({ project: p, phase: currentPhase(p), health: projectHealth(world, p).health }));
}
