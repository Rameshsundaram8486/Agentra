/* The scripted story the simulation plays. Events fire in order, `after` ticks after the previous one. An event
   with a `when` precondition waits until it holds (typically a human decision), so the demo never shows work that
   depends on a decision nobody has made. Stage 7 extends the script; the engine stays the same. */
import type { Decision, Execution, Task, World } from "@/types";
import { audit, logActivity, notify } from "@/store/actions";
import { byId } from "@/store/selectors";
import { secondsBetween, TICK_SECONDS } from "@/data/time";

export interface ScenarioEvent {
  id: string;
  after: number; // ticks after the previous scripted event
  when?: (world: World) => boolean;
  apply: (world: World) => void;
}

/* Helpers ------------------------------------------------------------------------------------------- */

function setTask(world: World, id: string, patch: Partial<Task>): void {
  const task = byId(world.tasks, id)!;
  if (patch.state === "in_progress" && !task.startedAt) task.startedAt = world.now;
  if (patch.state === "completed") task.completedAt = world.now;
  Object.assign(task, patch);
}

function setAgent(world: World, id: string, status: World["agents"][number]["status"], taskId?: string, projectId?: string): void {
  const agent = byId(world.agents, id)!;
  Object.assign(agent, { status, since: world.now, taskId, projectId: projectId ?? agent.projectId });
}

function start(world: World, execution: Pick<Execution, "id" | "agentId" | "title" | "input"> & Partial<Execution>): void {
  world.executions.unshift({
    status: "running", startedAt: world.now, attempt: 1, maxAttempts: 2, tokensIn: 12_000 + world.executions.length * 731, tokensOut: 0, costUsd: 0,
    logs: [{ at: world.now, level: "info", text: `Run started: ${execution.title}` }],
    ...execution,
  });
  const agent = byId(world.agents, execution.agentId)!;
  Object.assign(agent, { status: "working", since: world.now, taskId: execution.taskId, projectId: execution.projectId ?? agent.projectId, runs: agent.runs + 1 });
  if (execution.taskId) setTask(world, execution.taskId, { state: "in_progress", agentId: execution.agentId });
}

function finish(world: World, id: string, status: "succeeded" | "failed", output: string, tokensOut = 6_400): void {
  const execution = byId(world.executions, id)!;
  Object.assign(execution, { status, output, endedAt: world.now, tokensOut, costUsd: Math.round((execution.tokensIn * 4 + tokensOut * 20) / 10_000) / 100 });
  execution.logs.push({ at: world.now, level: status === "succeeded" ? "info" : "error", text: status === "succeeded" ? "Run succeeded" : `Run failed: ${output}` });
  const agent = byId(world.agents, execution.agentId)!;
  if (status === "succeeded") agent.succeeded += 1;
  else agent.failed += 1;
}

function running(world: World, id: string): boolean {
  return byId(world.executions, id)?.status === "running";
}

function runningFor(world: World, id: string, ticks: number): boolean {
  const execution = byId(world.executions, id);
  return execution?.status === "running" && secondsBetween(execution.startedAt, world.now) >= ticks * TICK_SECONDS;
}

/** No run of this agent is in flight (a person may have paused or retried something). */
function free(world: World, agentId: string): boolean {
  return !world.executions.some((e) => e.agentId === agentId && (e.status === "running" || e.status === "retrying" || e.status === "paused"));
}

function decided(world: World, id: string): boolean {
  const decision = byId(world.decisions, id);
  return decision?.status === "approved" || decision?.status === "modified";
}

function unblock(world: World, id: string, evidence: string, ref: string): void {
  const decision = byId(world.decisions, id)!;
  decision.blockedBy = undefined;
  decision.evidence.push({ label: evidence, ref });
  decision.history.push({ at: world.now, actor: "system", action: "comment", summary: evidence });
}

function addDecision(world: World, decision: Omit<Decision, "createdAt" | "history" | "status">): void {
  world.decisions.push({ ...decision, createdAt: world.now, status: "pending", history: [{ at: world.now, actor: decision.originAgentId, action: "raised", summary: "Raised" }] });
  audit(world, decision.originAgentId, "decision.raise", decision.code, decision.title);
}

function addVersion(world: World, artifactId: string, author: string, summary: string): void {
  const artifact = byId(world.artifacts, artifactId)!;
  const no = artifact.versions[artifact.versions.length - 1]!.no + 1;
  const sha = (artifactId + no).split("").reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7).toString(16).padStart(8, "0").repeat(8);
  artifact.versions.push({ no, at: world.now, author, summary, sha256: sha, status: "in_review" });
}

/* The script ---------------------------------------------------------------------------------------- */

/** The timeline: events in order, each `after` ticks after the previous one. */
export const TIMELINE: ScenarioEvent[] = [
  {
    id: "security-progress", after: 3, when: (w) => running(w, "x-103"),
    apply: (w) => {
      byId(w.executions, "x-103")!.logs.push({ at: w.now, level: "info", text: "SC-01 to SC-05 checked: no high-severity gaps" });
      logActivity(w, "info", "Security Reviewer Agent checked SC-01 to SC-05 of design v2: no high-severity gaps so far", { projectId: "p-power", agentId: "a-sec" });
    },
  },
  {
    id: "wi004-tests-pass", after: 5,
    apply: (w) => {
      unblock(w, "d-wi004", "Sandbox build and tests passed: 48 of 48 tests in 3 min 12 s (simulated sandbox VM)", "SBX-RUN-311");
      logActivity(w, "success", "Change set WI-004 v2 passed its sandbox build and tests; ready for a reviewer", { projectId: "p-spo", agentId: "a-dev2" });
      notify(w, "success", "WI-004 v2 is ready for approval", "Its sandbox build and tests passed.", "/decisions?id=d-wi004");
    },
  },
  {
    id: "regression-done", after: 6, when: (w) => running(w, "x-102"),
    apply: (w) => {
      finish(w, "x-102", "succeeded", "409 of 412 passed; the 3 failures are linked to DEF-014");
      setTask(w, "t-i1", { state: "completed" });
      setAgent(w, "a-qa1", "idle");
      addVersion(w, "doc-i-report", "a-qa1", "Run 3: 409 of 412 passed");
      logActivity(w, "success", "QA Agent finished regression run 3: 409 of 412 passed (3 failures linked to DEF-014)", { projectId: "p-intranet", agentId: "a-qa1" });
    },
  },
  {
    id: "owner-scan", after: 5, when: (w) => running(w, "x-104"),
    apply: (w) => {
      finish(w, "x-104", "succeeded", "Findings: DEC-006 overdue; INC-003 investigating; DEC-007 and DEC-005 due within a day");
      start(w, { id: "x-301", agentId: "a-po", title: "Portfolio health scan", input: "7 projects, open decisions, risks and incidents" });
      logActivity(w, "warning", "Project Owner Agent: DEC-006 (cut-over date) is overdue; SharePoint Online Migration stays critical until it is decided", { projectId: "p-spo", agentId: "a-po" });
      notify(w, "critical", "Overdue decision: cut-over date", "DEC-006 is past its deadline. The Project Owner Agent recommends moving cut-over by one week.", "/decisions?id=d-cutover");
    },
  },
  {
    id: "security-review-done", after: 6, when: (w) => running(w, "x-103"),
    apply: (w) => {
      finish(w, "x-103", "succeeded", "Review of design v2: no high-severity gaps; SC-06 and SC-08 medium with mitigations");
      setTask(w, "t-p3", { state: "waiting_for_review" });
      setAgent(w, "a-sec", "waiting_approval", "t-p3");
      addVersion(w, "doc-p-sec", "a-sec", "Review of design v2: no high gaps; 2 medium");
      unblock(w, "d-secreview", "Security review v2 is complete: no high-severity gaps", "SEC-REV-v2");
      notify(w, "info", "Security review ready for sign-off", "Review v2 of the Power Platform design has no high-severity gaps.", "/decisions?id=d-secreview");
      logActivity(w, "success", "Security Reviewer Agent completed the review of design v2: no high-severity gaps", { projectId: "p-power", agentId: "a-sec" });
    },
  },
  {
    id: "wi005-submitted", after: 6, when: (w) => running(w, "x-101"),
    apply: (w) => {
      finish(w, "x-101", "succeeded", "Change set WI-005 v1: 7 files, 3 test files; sandbox run queued", 12_100);
      setTask(w, "t-s5", { state: "waiting_for_review" });
      setAgent(w, "a-dev1", "waiting_approval", "t-s5");
      w.artifacts.push({
        id: "doc-s-cs5", projectId: "p-spo", phase: 9, type: "change_set", title: "Change set WI-005", ownerId: "u-priya", sourceAgentId: "a-dev1", traces: ["WI-005", "ENT-003", "INT-002"],
        excerpt: "Maps 2,140 terms to 9 term sets and preserves managed metadata on migrated items; 3 test files.",
        versions: [{ no: 1, at: w.now, author: "a-dev1", summary: "First version", sha256: "4be1c07d9a2f6e3b8c5d1a0f7e9b2c4d6a8f0e1d3c5b7a9e2f4d6c8b0a1e3f5d", status: "in_review" }],
      });
      addDecision(w, {
        id: "d-wi005", taskId: "t-s5", artifactId: "doc-s-cs5", code: "DEC-013", projectId: "p-spo", phase: 9, kind: "approval", priority: "medium", title: "Approve change set WI-005 v1 (managed metadata)",
        question: "Approve the change set? It must pass its sandbox build and tests first.", originAgentId: "a-dev1", allowedRoles: ["reviewer"], deadline: w.now.replace(/T.*/, "T14:00:00.000Z"),
        options: [{ key: "approve", title: "Approve and merge", description: "Agentra merges it into main and completes WI-005.", pros: [], cons: [] }, { key: "changes", title: "Request changes", description: "Send it back with comments.", pros: [], cons: [] }],
        recommended: "approve", rationale: "All 14 mapping rules have tests; 2,140 of 2,140 terms map to a term set.", risks: ["The pilot migration waits for this and WI-004"],
        evidence: [{ label: "Change set WI-005 v1: 7 files", ref: "CS-WI-005-v1" }], blockedBy: "Its sandbox build and test run has not finished yet",
      });
      logActivity(w, "info", "Developer Agent submitted change set WI-005 v1; sandbox build and tests queued", { projectId: "p-spo", agentId: "a-dev1" });
    },
  },
  {
    id: "performance-retry", after: 5, when: (w) => byId(w.executions, "x-108")?.status === "failed" && free(w, "a-qa2"),
    apply: (w) => {
      byId(w.incidents, "inc-2")!.status = "investigating";
      start(w, { id: "x-302", agentId: "a-qa2", projectId: "p-intranet", taskId: "t-i5", title: "Performance test on the previous load generator image", input: "Load profile v1, image win-load@3 (previous), 500 virtual users" });
      logActivity(w, "info", "QA Agent 2 is rerunning the performance test on the previous load generator image (INC-002 containment)", { projectId: "p-intranet", agentId: "a-qa2" });
    },
  },
  {
    id: "leads-done", after: 6, when: (w) => running(w, "x-112"),
    apply: (w) => {
      finish(w, "x-112", "succeeded", "4 of 12 leads qualified (Preview)");
      setAgent(w, "a-lead", "idle");
      logActivity(w, "info", "Lead Generation Agent qualified 4 of 12 inbound leads (Preview, not in the MVP)", { agentId: "a-lead" });
    },
  },
  {
    id: "wi005-tests-pass", after: 5, when: (w) => byId(w.decisions, "d-wi005") !== undefined,
    apply: (w) => {
      unblock(w, "d-wi005", "Sandbox build and tests passed: 61 of 61 tests (simulated sandbox VM)", "SBX-RUN-318");
      logActivity(w, "success", "Change set WI-005 v1 passed its sandbox build and tests; ready for a reviewer", { projectId: "p-spo", agentId: "a-dev1" });
      notify(w, "success", "WI-005 v1 is ready for approval", "Its sandbox build and tests passed.", "/decisions?id=d-wi005");
    },
  },
  {
    id: "performance-done", after: 7, when: (w) => runningFor(w, "x-302", 6),
    apply: (w) => {
      finish(w, "x-302", "succeeded", "p95 page load 1.8 s at 500 users (target 2.5 s)");
      setTask(w, "t-i5", { state: "completed" });
      setAgent(w, "a-qa2", "idle");
      const incident = byId(w.incidents, "inc-2")!;
      incident.status = "resolved";
      incident.rca.facts.push("The rerun on the previous image completed normally");
      logActivity(w, "success", "QA Agent 2: performance test passed (p95 1.8 s at 500 users); INC-002 resolved, awaiting verification", { projectId: "p-intranet", agentId: "a-qa2" });
    },
  },
  {
    id: "status-updates", after: 6,
    apply: (w) => logActivity(w, "info", "Project Manager Agent sent status updates for 5 active projects to their project managers", { agentId: "a-pm" }),
  },
];

/** Follow-ups to human decisions and to finished work. Checked on every tick, whatever the timeline has reached;
    each fires once, as soon as its precondition holds. */
export const REACTIONS: ScenarioEvent[] = [
  {
    id: "requirements-redraft-start", after: 2, when: (w) => decided(w, "d-platform") && free(w, "a-ba"),
    apply: (w) => {
      start(w, { id: "x-303", agentId: "a-ba", projectId: "p-workflow", taskId: "t-w2", title: "Redraft requirements with the platform decision", input: "Brief, interview notes, DEC-001 outcome", handoffTo: "solution_architect" });
      logActivity(w, "info", "Business Analyst Agent resumed drafting the requirements with the platform decision", { projectId: "p-workflow", agentId: "a-ba" });
    },
  },
  {
    id: "requirements-redraft-done", after: 1, when: (w) => runningFor(w, "x-303", 8),
    apply: (w) => {
      finish(w, "x-303", "succeeded", "Requirements baseline v2: 38 requirements, 61 acceptance criteria, traceability complete", 15_800);
      setTask(w, "t-w2", { state: "waiting_for_review" });
      setAgent(w, "a-ba", "waiting_approval", "t-w2");
      addVersion(w, "doc-w-brd", "a-ba", "38 requirements with the platform decision");
      byId(w.projects, "p-workflow")!.phases[6]!.progress = 70;
      addDecision(w, {
        id: "d-brd", taskId: "t-w2", artifactId: "doc-w-brd", code: "DEC-014", projectId: "p-workflow", phase: 7, kind: "approval", priority: "high", title: "Approve the requirements baseline v2",
        question: "Approve requirements v2 as the baseline? Once approved it changes only through change requests.", originAgentId: "a-ba", allowedRoles: ["reviewer", "owner"], deadline: w.now.replace(/T.*/, "T15:00:00.000Z"),
        options: [{ key: "approve", title: "Approve the baseline", description: "Locks the requirements under change control.", pros: [], cons: [] }, { key: "changes", title: "Request changes", description: "Send it back with comments.", pros: [], cons: [] }],
        recommended: "approve", rationale: "All 38 requirements have acceptance criteria and sources; no open questions remain.", risks: [], evidence: [{ label: "Business requirements v2", ref: "BRD-v2" }],
      });
      logActivity(w, "success", "Business Analyst Agent submitted requirements v2 for review (38 requirements)", { projectId: "p-workflow", agentId: "a-ba" });
    },
  },
  {
    id: "def014-fix-start", after: 1, when: (w) => decided(w, "d-def014") && free(w, "a-dev2"),
    apply: (w) => {
      start(w, { id: "x-304", agentId: "a-dev2", projectId: "p-intranet", taskId: "t-i6", title: "Fix DEF-014: permission trimming in search results", input: "DEF-014 reproduction steps, search web part source", handoffTo: "qa_tester" });
      logActivity(w, "info", "Developer Agent 2 started the DEF-014 fix", { projectId: "p-intranet", agentId: "a-dev2" });
    },
  },
  {
    id: "def014-fix-done", after: 1, when: (w) => runningFor(w, "x-304", 7),
    apply: (w) => {
      finish(w, "x-304", "succeeded", "Fixed and retested: 18 of 18 permission tests pass");
      setTask(w, "t-i6", { state: "completed" });
      setAgent(w, "a-dev2", "idle");
      byId(w.risks, "r3")!.status = "closed";
      logActivity(w, "success", "DEF-014 fixed and retested: 18 of 18 permission tests pass; RSK-003 closed", { projectId: "p-intranet", agentId: "a-dev2" });
    },
  },
  {
    id: "pilot-ready", after: 1, when: (w) => decided(w, "d-wi004") && decided(w, "d-wi005"),
    apply: (w) => {
      setTask(w, "t-s6", { state: "ready" });
      byId(w.projects, "p-spo")!.phases[8]!.progress = 72;
      logActivity(w, "info", "WI-004 and WI-005 are merged: the pilot migration (WI-006) can start", { projectId: "p-spo" });
    },
  },
];
