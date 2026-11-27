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
  reopen: "pending",
};

/** Actions that settle a decision (the others ask, suggest, set aside or reopen it). */
const SETTLING: DecisionAction[] = ["accept", "choose_option", "custom", "reject"];

export function decide(world: World, input: DecisionInput): World {
  const decision = byId(world.decisions, input.decisionId);
  if (!decision) throw new DemoRuleError("Decision not found");
  let action = input.action;
  // An approval is approved or sent back: choosing its other option ("Request changes") is a rejection.
  if (decision.kind === "approval" && action === "choose_option" && input.optionKey && input.optionKey !== decision.recommended) action = "reject";
  if (decision.kind === "approval" && action === "custom") {
    throw new DemoRuleError("An approval is approved or sent back. To approve with conditions, accept it and add your constraints");
  }
  if (action === "reopen") {
    if (decision.status !== "deferred") throw new DemoRuleError(`Only a deferred decision can be reopened; ${decision.code} is ${decision.status.replace("_", " ")}`);
  } else if (!isOpenDecision(decision)) {
    throw new DemoRuleError(`${decision.code} is already ${decision.status.replace("_", " ")}`);
  }
  // Anyone may add a suggestion; only the listed roles decide, ask, defer or reopen.
  if (action !== "comment" && !decision.allowedRoles.includes(input.role)) {
    throw new DemoRuleError(`Only ${decision.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")} may decide ${decision.code}; you are acting as ${ROLE_LABELS[input.role].toLowerCase()}`);
  }
  if (SETTLING.includes(action) && decision.blockedBy) throw new DemoRuleError(`Cannot decide yet: ${decision.blockedBy}`);
  const comment = input.comment?.trim();
  if ((action === "reject" || action === "clarify" || action === "comment") && !comment) {
    throw new DemoRuleError(action === "reject" ? "Add a comment explaining your reason" : action === "clarify" ? "Write your question for the agent" : "Write your suggestion");
  }
  if (action === "custom" && !input.custom?.trim()) throw new DemoRuleError("Describe your own option");
  if (action === "choose_option" && !decision.options.some((o) => o.key === input.optionKey)) throw new DemoRuleError("Choose one of the options");

  return mutate(world, (draft) => {
    const target = byId(draft.decisions, decision.id)!;
    const who = actorName(draft, input.personId);
    let status = ACTION_STATUS[action];
    const accepted = action === "accept" ? target.recommended : action === "choose_option" ? input.optionKey : undefined;
    if (action === "choose_option" && accepted !== target.recommended) status = "modified";
    const chosen = target.options.find((o) => o.key === accepted);
    const sentBack = target.kind === "approval" && action === "reject";
    const summary =
      action === "comment" ? `Suggested: ${comment}`
      : action === "clarify" ? `Asked for clarification: ${comment}`
      : action === "custom" ? `Chose their own option: ${input.custom!.trim()}`
      : action === "reject" ? `${sentBack ? "Sent it back" : "Rejected the recommendation"}: ${comment}`
      : action === "defer" ? `Deferred${comment ? `: ${comment}` : ""}`
      : action === "reopen" ? `Reopened${comment ? `: ${comment}` : ""}`
      : `Chose "${chosen?.title}"${accepted === target.recommended ? " (the recommendation)" : " instead of the recommendation"}`;
    target.history.push({ at: draft.now, actor: input.personId, action, summary });
    if (status) {
      target.status = status;
      if (action === "reopen") target.outcome = undefined;
      else if (status !== "clarification_requested") {
        const outcome: DecisionOutcome = { action, by: input.personId, at: draft.now };
        if (accepted) outcome.optionKey = accepted;
        if (input.custom?.trim()) outcome.custom = input.custom.trim();
        if (comment) outcome.comment = comment;
        if (input.constraints?.trim()) outcome.constraints = input.constraints.trim();
        const artifact = byId(draft.artifacts, target.artifactId);
        if (artifact && (status === "approved" || status === "modified")) {
          const version = artifact.versions[artifact.versions.length - 1]!;
          outcome.boundTo = { artifactId: artifact.id, version: version.no, sha256: version.sha256 };
        }
        target.outcome = outcome;
      }
    }
    const bound = target.outcome?.boundTo && SETTLING.includes(action) ? ` (bound to v${target.outcome.boundTo.version}, sha256 ${target.outcome.boundTo.sha256.slice(0, 12)}…)` : "";
    const auditAction = action === "comment" ? "decision.suggest" : action === "clarify" ? "decision.clarify" : action === "reopen" ? "decision.reopen" : "decision.outcome";
    audit(draft, input.personId, auditAction, target.code, summary + bound);
    const severity: Severity = status === "rejected" ? "warning" : status === "approved" || status === "modified" ? "success" : "info";
    logActivity(draft, severity, `${who} ${summary.charAt(0).toLowerCase()}${summary.slice(1)} on ${target.code}: ${target.title}`, { projectId: target.projectId, link: `/decisions?id=${target.id}` });
    if (status === "approved" || status === "modified") DECISION_EFFECTS[target.id]?.(draft, target);
    if (status === "rejected") sendBack(draft, target);
  });
}

/** A rejected approval returns the work to its agent: the version is marked for changes, the task reopens (or is
    cancelled if it never started) and the agent is released. */
function sendBack(world: World, decision: Decision): void {
  if (decision.kind !== "approval") return;
  const artifact = byId(world.artifacts, decision.artifactId);
  if (artifact) Object.assign(artifact.versions[artifact.versions.length - 1]!, { status: "changes_requested", reviewedBy: decision.outcome?.by });
  const task = byId(world.tasks, decision.taskId);
  if (!task) return;
  task.state = task.startedAt ? "changes_requested" : "cancelled";
  for (const agent of world.agents) {
    if (agent.taskId === task.id && agent.status === "waiting_approval") Object.assign(agent, { status: "idle", taskId: undefined, since: world.now });
  }
  const outcome = task.state === "cancelled" ? "cancelled" : "sent back for changes";
  logActivity(world, "warning", `${task.key} ${outcome} after ${decision.code}`, { projectId: decision.projectId, agentId: task.agentId });
}

/** The agent that raised a decision answers a person's question about it; the decision is open again. */
export function answerClarification(world: World, decision: Decision): void {
  const question = [...decision.history].reverse().find((e) => e.action === "clarify");
  const answer = CLARIFICATION_ANSWERS[decision.id] ?? `${decision.rationale} Evidence: ${decision.evidence.map((e) => e.ref).join(", ")}.`;
  decision.history.push({ at: world.now, actor: decision.originAgentId, action: "answered", summary: answer });
  decision.status = "pending";
  const agent = actorName(world, decision.originAgentId);
  audit(world, decision.originAgentId, "decision.answer", decision.code, answer);
  logActivity(world, "info", `${agent} answered the question on ${decision.code}; it is waiting for a decision again`, { projectId: decision.projectId, agentId: decision.originAgentId, link: `/decisions?id=${decision.id}` });
  notify(world, "info", `${decision.code} answered`, `${agent} answered the question from ${question ? actorName(world, question.actor) : "a reviewer"}.`, `/decisions?id=${decision.id}`);
}

/** Answers grounded in each decision's evidence; other decisions answer from their rationale and evidence. */
const CLARIFICATION_ANSWERS: Record<string, string> = {
  "d-platform": "Premium connectors are needed only for the 3 flows that call the property management system; the other 11 flows use standard connectors included in Microsoft 365 E3 (brief v2, section 3).",
  "d-wi004": "The tests cover lists of 5,000, 50,000 and 250,000 items; the batch size is read from configuration (default 2,000), as REV-1 asked.",
  "d-cutover": "24 December still leaves 3 working days before the customer's year-end freeze; extending the old farm licences costs about AED 4,500 (MTG-1104).",
  "d-def014": "3 of 18 permission tests failed, all on HR libraries with unique permissions; the hotfix is about 1 day plus 1 day of retest (QA-06).",
  "d-uat-signoff": "UF-07 asks for a new monthly storage report that is not in the approved requirements, so it is new scope, not a defect (UAT report v1).",
};

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
