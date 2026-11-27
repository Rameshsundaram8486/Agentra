/* Changes to the demo world, as pure functions: each takes a world and returns a new one, or throws DemoRuleError
   with the reason a person may not do it. The same rules as the real Agentra apply in the demo: only the listed
   roles decide, agents never approve, an approval waits until its evidence is in place (blockedBy), and the
   agent's recommendation is never overwritten. */
import type { ActivityEvent, Decision, DecisionAction, DecisionOutcome, Role, Severity, World } from "@/types";
import { addSeconds } from "@/data/time";
import { actorName, byId, isOpenDecision } from "./selectors";

export class DemoRuleError extends Error {}

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  project_manager: "Project manager",
  reviewer: "Reviewer",
  customer_approver: "Customer approver",
};

/** Runs `change` on a copy of the world and returns the copy. */
export function mutate(world: World, change: (draft: World) => void): World {
  const draft = structuredClone(world);
  change(draft);
  return draft;
}

/** A new record id, numbered from the world's own counter, so ids are deterministic and survive reloads. */
export function newId(world: World, prefix: string): string {
  world.seq += 1;
  return `${prefix}-${world.seq}`;
}

export function logActivity(world: World, severity: Severity, text: string, extra: Partial<ActivityEvent> = {}): void {
  world.activity.unshift({ id: newId(world, "ev"), at: world.now, severity, text, ...extra });
  world.activity.length = Math.min(world.activity.length, 80);
}

export function notify(world: World, severity: Severity, title: string, body: string, link?: string): void {
  world.notifications.unshift({ id: newId(world, "n"), at: world.now, title, body, severity, read: false, link });
  world.notifications.length = Math.min(world.notifications.length, 40);
}

export function audit(world: World, actor: string, action: string, target: string, detail?: string): void {
  world.audit.unshift({ id: newId(world, "au"), at: world.now, actor, action, target, detail });
}

/* Decisions ----------------------------------------------------------------------------------------- */

export interface DecisionInput {
  decisionId: string;
  action: DecisionAction;
  optionKey?: string;
  custom?: string;
  comment?: string;
  constraints?: string;
  personId: string;
  role: Role;
}

const ACTION_STATUS: Record<DecisionAction, Decision["status"] | null> = {
  accept: "approved",
  choose_option: "approved", // "modified" when the chosen option is not the recommended one
  custom: "modified",
  reject: "rejected",
  defer: "deferred",
  clarify: "clarification_requested",
  comment: null, // adds a suggestion without deciding
};

export function decide(world: World, input: DecisionInput): World {
  const decision = byId(world.decisions, input.decisionId);
  if (!decision) throw new DemoRuleError("Decision not found");
  if (!isOpenDecision(decision)) throw new DemoRuleError(`${decision.code} is already ${decision.status.replace("_", " ")}`);
  if (!decision.allowedRoles.includes(input.role)) {
    throw new DemoRuleError(`Only ${decision.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")} may decide ${decision.code}; you are acting as ${ROLE_LABELS[input.role].toLowerCase()}`);
  }
  const deciding = input.action !== "comment" && input.action !== "clarify" && input.action !== "defer";
  if (deciding && decision.blockedBy && input.action !== "reject") throw new DemoRuleError(`Cannot approve yet: ${decision.blockedBy}`);
  const comment = input.comment?.trim();
  if ((input.action === "reject" || input.action === "clarify" || input.action === "comment") && !comment) {
    throw new DemoRuleError("Add a comment explaining your reason or question");
  }
  if (input.action === "custom" && !input.custom?.trim()) throw new DemoRuleError("Describe your own option");
  if (input.action === "choose_option" && !decision.options.some((o) => o.key === input.optionKey)) throw new DemoRuleError("Choose one of the options");

  return mutate(world, (draft) => {
    const target = byId(draft.decisions, decision.id)!;
    const who = actorName(draft, input.personId);
    let status = ACTION_STATUS[input.action];
    const accepted = input.action === "accept" ? target.recommended : input.optionKey;
    if (input.action === "choose_option" && accepted !== target.recommended) status = "modified";
    const chosen = target.options.find((o) => o.key === accepted);
    const summary =
      input.action === "comment" ? `Suggested: ${comment}`
      : input.action === "clarify" ? `Asked for clarification: ${comment}`
      : input.action === "custom" ? `Chose their own option: ${input.custom!.trim()}`
      : input.action === "reject" ? `Rejected the recommendation: ${comment}`
      : input.action === "defer" ? `Deferred${comment ? `: ${comment}` : ""}`
      : `Chose "${chosen?.title}"${accepted === target.recommended ? " (the recommendation)" : " instead of the recommendation"}`;
    target.history.push({ at: draft.now, actor: input.personId, action: input.action, summary });
    if (status) {
      target.status = status;
      const outcome: DecisionOutcome = { action: input.action, by: input.personId, at: draft.now };
      if (accepted) outcome.optionKey = accepted;
      if (input.custom?.trim()) outcome.custom = input.custom.trim();
      if (comment) outcome.comment = comment;
      if (input.constraints?.trim()) outcome.constraints = input.constraints.trim();
      if (status !== "clarification_requested") target.outcome = outcome;
    }
    audit(draft, input.personId, input.action === "comment" ? "decision.suggest" : "decision.outcome", target.code, summary);
    const severity: Severity = status === "rejected" ? "warning" : status === "approved" || status === "modified" ? "success" : "info";
    logActivity(draft, severity, `${who} ${summary.charAt(0).toLowerCase()}${summary.slice(1)} on ${target.code}: ${target.title}`, { projectId: target.projectId });
    if (status === "approved" || status === "modified") DECISION_EFFECTS[target.id]?.(draft, target);
  });
}

/** What a decided decision changes right away elsewhere in the world (follow-up work is scripted in the simulation). */
const DECISION_EFFECTS: Record<string, (world: World, decision: Decision) => void> = {
  "d-platform": (world, decision) => {
    const choice = decision.outcome?.custom ?? decision.options.find((o) => o.key === decision.outcome?.optionKey)?.title;
    logActivity(world, "info", `Business Analyst Agent will redraft the requirements for: ${choice}`, { projectId: decision.projectId, agentId: "a-ba" });
  },
  "d-cutover": (world, decision) => {
    const project = byId(world.projects, "p-spo")!;
    const cutover = project.milestones.find((m) => m.title.startsWith("Full migration"));
    const risk = byId(world.risks, "r1")!;
    if (decision.outcome?.optionKey === "move" && cutover) {
      cutover.due = addSeconds(cutover.due, 7 * 86_400);
      risk.status = "mitigating";
      risk.likelihood = 2;
      logActivity(world, "success", "Cut-over moved to 24 December; RSK-001 now mitigated", { projectId: project.id });
    } else if (decision.outcome?.optionKey === "phase") {
      risk.status = "mitigating";
      risk.likelihood = 3;
      logActivity(world, "info", "Cut-over split: finance sites first; RSK-001 being mitigated", { projectId: project.id });
    }
  },
  "d-def014": (world, decision) => {
    const fix = byId(world.tasks, "t-i6")!;
    const risk = byId(world.risks, "r3")!;
    risk.status = "mitigating";
    if (decision.outcome?.optionKey === "exclude") risk.likelihood = 2;
    fix.state = "ready";
    logActivity(world, "info", "DEF-014 fix is ready to start; RSK-003 being mitigated", { projectId: decision.projectId });
  },
  "d-wi004": (world) => {
    const task = byId(world.tasks, "t-s4")!;
    task.state = "completed";
    task.completedAt = world.now;
    const doc = byId(world.artifacts, "doc-s-cs4")!;
    doc.versions[doc.versions.length - 1]!.status = "approved";
    const dev = byId(world.agents, "a-dev2")!;
    if (dev.taskId === "t-s4") Object.assign(dev, { status: "idle", taskId: undefined, since: world.now });
    logActivity(world, "success", "Agentra merged change set WI-004 v2 into main; WI-004 completed", { projectId: "p-spo", agentId: "a-dev2" });
  },
  "d-wi005": (world) => {
    const task = byId(world.tasks, "t-s5")!;
    Object.assign(task, { state: "completed", completedAt: world.now });
    const doc = byId(world.artifacts, "doc-s-cs5");
    if (doc) doc.versions[doc.versions.length - 1]!.status = "approved";
    const dev = byId(world.agents, "a-dev1")!;
    if (dev.taskId === "t-s5") Object.assign(dev, { status: "idle", taskId: undefined, since: world.now });
    logActivity(world, "success", "Agentra merged change set WI-005 v1 into main; WI-005 completed", { projectId: "p-spo", agentId: "a-dev1" });
  },
  "d-brd": (world) => {
    const doc = byId(world.artifacts, "doc-w-brd")!;
    doc.versions[doc.versions.length - 1]!.status = "approved";
    const task = byId(world.tasks, "t-w2")!;
    Object.assign(task, { state: "completed", completedAt: world.now });
    const agent = byId(world.agents, "a-ba")!;
    if (agent.taskId === "t-w2") Object.assign(agent, { status: "completed", taskId: undefined, since: world.now });
    byId(world.projects, "p-workflow")!.phases[6]!.progress = 85;
    logActivity(world, "success", "Requirements baseline v2 approved and locked under change control", { projectId: "p-workflow" });
  },
  "d-uat-signoff": (world) => {
    const project = byId(world.projects, "p-spse")!;
    const uat = project.phases[10]!;
    Object.assign(uat, { state: "completed", progress: 100, completedAt: world.now, gateApprovedBy: "u-daniel" });
    Object.assign(project.phases[11]!, { state: "active", progress: 5, startedAt: world.now });
    const task = byId(world.tasks, "t-u5")!;
    Object.assign(task, { state: "completed", completedAt: world.now });
    const signoff = byId(world.artifacts, "doc-u-signoff")!;
    signoff.versions[signoff.versions.length - 1]!.status = "approved";
    byId(world.risks, "r5")!.status = "closed";
    const agent = byId(world.agents, "a-uat")!;
    Object.assign(agent, { status: "completed", taskId: undefined, since: world.now });
    logActivity(world, "success", "Customer signed off UAT; the upgrade moves to Production Go-Live (Preview)", { projectId: project.id });
  },
  "d-secreview": (world) => {
    const doc = byId(world.artifacts, "doc-p-sec")!;
    doc.versions[doc.versions.length - 1]!.status = "approved";
    const task = byId(world.tasks, "t-p3")!;
    Object.assign(task, { state: "completed", completedAt: world.now });
    const agent = byId(world.agents, "a-sec")!;
    if (agent.taskId === "t-p3") Object.assign(agent, { status: "idle", taskId: undefined, since: world.now });
  },
};

/* Notifications and executions ---------------------------------------------------------------------- */

export function markNotificationsRead(world: World, ids?: string[]): World {
  return mutate(world, (draft) => {
    for (const n of draft.notifications) if (!ids || ids.includes(n.id)) n.read = true;
  });
}

const CONTROLLERS: Role[] = ["owner", "project_manager"];

/** Pause, resume or retry a simulated execution. Only owners and project managers control agent runs. */
export function controlExecution(world: World, executionId: string, command: "pause" | "resume" | "retry", personId: string, role: Role): World {
  if (!CONTROLLERS.includes(role)) throw new DemoRuleError(`Only an owner or a project manager may ${command} agent runs; you are acting as ${ROLE_LABELS[role].toLowerCase()}`);
  const execution = byId(world.executions, executionId);
  if (!execution) throw new DemoRuleError("Execution not found");
  const allowed = { pause: ["running"], resume: ["paused"], retry: ["failed"] }[command];
  if (!allowed.includes(execution.status)) throw new DemoRuleError(`A ${execution.status} run cannot be ${command === "retry" ? "retried" : `${command}d`}`);
  if (command === "retry" && execution.attempt >= execution.maxAttempts + 1) throw new DemoRuleError("No retries left; raise it with the Project Owner Agent");
  if (command !== "pause") {
    const busy = world.executions.find((e) => e.agentId === execution.agentId && e.id !== executionId && (e.status === "running" || e.status === "retrying"));
    if (busy) throw new DemoRuleError(`${actorName(world, execution.agentId)} is busy with "${busy.title}"; try again when it finishes`);
  }
  return mutate(world, (draft) => {
    const target = byId(draft.executions, executionId)!;
    const who = actorName(draft, personId);
    if (command === "pause") target.status = "paused";
    if (command === "resume") target.status = "running";
    if (command === "retry") {
      Object.assign(target, { status: "retrying", attempt: target.attempt + 1, endedAt: undefined, output: undefined, finishAt: draft.sim.elapsed + 8 });
    }
    target.logs.push({ at: draft.now, level: "info", text: `${who} ${command === "retry" ? "asked for a retry" : `${command}d the run`} (simulated)` });
    const agent = byId(draft.agents, target.agentId);
    if (agent && command !== "pause") Object.assign(agent, { status: "working", since: draft.now, taskId: target.taskId ?? agent.taskId, projectId: target.projectId ?? agent.projectId });
    if (agent && command === "pause") Object.assign(agent, { status: "idle", since: draft.now });
    const task = byId(draft.tasks, target.taskId);
    if (task && command === "retry" && (task.state === "failed" || task.state === "blocked")) task.state = "in_progress";
    audit(draft, personId, `execution.${command}`, target.title);
    logActivity(draft, "info", `${who} ${command === "retry" ? "retried" : `${command}d`} "${target.title}" (simulated)`, { projectId: target.projectId, agentId: target.agentId });
  });
}
