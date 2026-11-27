/* Derived views of human decisions for the Decision Center: the queues, what the agents recommended against what
   people decided, the records a decision refers to, and what a decision changed. Nothing here is stored. */
import type { ActivityEvent, Artifact, Decision, Incident, Risk, Role, World } from "@/types";
import { secondsBetween } from "@/data/time";
import { isOpenDecision, isOverdue, priorityRank } from "./selectors";

export type DecisionQueue = "pending" | "high" | "overdue" | "approved" | "rejected" | "deferred" | "all";

export const QUEUES: { id: DecisionQueue; label: string; hint: string }[] = [
  { id: "pending", label: "Pending", hint: "waiting for a person" },
  { id: "high", label: "High priority", hint: "critical or high, open" },
  { id: "overdue", label: "Overdue", hint: "past their deadline" },
  { id: "approved", label: "Recently approved", hint: "in the last 30 days" },
  { id: "rejected", label: "Rejected", hint: "rejected or sent back" },
  { id: "deferred", label: "Deferred", hint: "a decider can reopen" },
  { id: "all", label: "All", hint: "every decision" },
];

const RECENT_SECONDS = 30 * 86_400;

export function inQueue(world: World, decision: Decision, queue: DecisionQueue): boolean {
  switch (queue) {
    case "pending": return isOpenDecision(decision);
    case "high": return isOpenDecision(decision) && (decision.priority === "critical" || decision.priority === "high");
    case "overdue": return isOverdue(decision, world.now);
    case "approved": return (decision.status === "approved" || decision.status === "modified") && !!decision.outcome && secondsBetween(decision.outcome.at, world.now) <= RECENT_SECONDS;
    case "rejected": return decision.status === "rejected";
    case "deferred": return decision.status === "deferred";
    case "all": return true;
  }
}

/** Open decisions first (most urgent, then nearest deadline), then decided ones, newest first. */
export function sortDecisions(decisions: Decision[]): Decision[] {
  return [...decisions].sort((a, b) => {
    const openA = isOpenDecision(a) ? 0 : 1;
    const openB = isOpenDecision(b) ? 0 : 1;
    if (openA !== openB) return openA - openB;
    if (openA === 0) return priorityRank(a.priority) - priorityRank(b.priority) || Date.parse(a.deadline) - Date.parse(b.deadline);
    return Date.parse(b.outcome?.at ?? b.createdAt) - Date.parse(a.outcome?.at ?? a.createdAt);
  });
}

export function canDecide(decision: Decision, role: Role): boolean {
  return decision.allowedRoles.includes(role);
}

/** The option the agent recommended and the option or text people chose. */
export function recommendedOption(decision: Decision) {
  return decision.options.find((o) => o.key === decision.recommended);
}

export function humanChoice(decision: Decision): string | undefined {
  const outcome = decision.outcome;
  if (!outcome) return undefined;
  if (outcome.custom) return outcome.custom;
  if (outcome.action === "reject") return decision.kind === "approval" ? "Sent back for changes" : "Rejected the recommendation";
  if (outcome.action === "defer") return "Deferred";
  return decision.options.find((o) => o.key === outcome.optionKey)?.title;
}

/** How people answered agent recommendations: kept as recommended, changed, rejected or deferred. */
export function recommendationStats(decisions: Decision[]) {
  const decided = decisions.filter((d) => d.outcome);
  const asRecommended = decided.filter((d) => d.status === "approved").length;
  const changed = decided.filter((d) => d.status === "modified").length;
  const rejected = decided.filter((d) => d.status === "rejected").length;
  const deferred = decided.filter((d) => d.status === "deferred").length;
  const settled = asRecommended + changed + rejected;
  return { open: decisions.filter(isOpenDecision).length, asRecommended, changed, rejected, deferred, agreement: settled ? Math.round((asRecommended / settled) * 100) : null };
}

/** Risks, incidents and documents a decision's evidence refers to, as they are now. */
export function linkedRecords(world: World, decision: Decision): { risks: Risk[]; incidents: Incident[]; artifacts: Artifact[] } {
  const refs = new Set(decision.evidence.map((e) => e.ref));
  const text = `${decision.rationale} ${decision.question} ${decision.risks.join(" ")}`;
  const mentioned = (code: string) => refs.has(code) || text.includes(code);
  return {
    risks: world.risks.filter((r) => mentioned(r.code) || r.mitigation.includes(decision.code)),
    incidents: world.incidents.filter((i) => mentioned(i.code)),
    artifacts: world.artifacts.filter((a) => a.id === decision.artifactId),
  };
}

/** What happened in the world when the decision was made: the decision itself and its effects. */
export function decisionEffects(world: World, decision: Decision): ActivityEvent[] {
  const outcome = decision.outcome;
  if (!outcome) return [];
  return world.activity.filter((e) => e.at === outcome.at && e.projectId === decision.projectId).reverse();
}

/** The audit entries about a decision, newest first. */
export function decisionAudit(world: World, decision: Decision) {
  return world.audit.filter((a) => a.target === decision.code);
}
