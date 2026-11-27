import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { invariantProblems } from "@/test/invariants";
import { controlExecution, decide, DemoRuleError } from "./actions";
import { byId, kpis, projectHealth } from "./selectors";

const OWNER = { personId: "u-rania", role: "owner" as const };
const REVIEWER = { personId: "u-priya", role: "reviewer" as const };
const PM = { personId: "u-omar", role: "project_manager" as const };

describe("human decisions", () => {
  it("keeps the agent's recommendation and records the human choice separately", () => {
    const before = createSeedWorld();
    const after = decide(before, {
      decisionId: "d-platform", action: "choose_option", optionKey: "hybrid", comment: "Finance documents stay on premises", constraints: "Purchase orders above AED 50,000", ...OWNER,
    });
    const decision = byId(after.decisions, "d-platform")!;
    expect(decision.recommended).toBe("spo");
    expect(decision.status).toBe("modified");
    expect(decision.outcome).toMatchObject({ action: "choose_option", optionKey: "hybrid", constraints: "Purchase orders above AED 50,000", by: "u-rania" });
    expect(decision.history.at(-1)!.summary).toBe('Chose "Hybrid" instead of the recommendation');
    expect(after.audit[0]).toMatchObject({ actor: "u-rania", action: "decision.outcome", target: "DEC-001" });
    expect(byId(before.decisions, "d-platform")!.status).toBe("pending"); // the original world is unchanged
    expect(invariantProblems(after)).toEqual([]);
  });

  it("accepting the recommendation approves it; a custom option is recorded as a modification", () => {
    expect(byId(decide(createSeedWorld(), { decisionId: "d-platform", action: "accept", ...OWNER }).decisions, "d-platform")!.status).toBe("approved");
    const custom = decide(createSeedWorld(), { decisionId: "d-platform", action: "custom", custom: "Power Apps on Dataverse", ...PM });
    expect(byId(custom.decisions, "d-platform")!.outcome).toMatchObject({ action: "custom", custom: "Power Apps on Dataverse" });
    expect(byId(custom.decisions, "d-platform")!.status).toBe("modified");
  });

  it("refuses roles that may not decide, with the reason", () => {
    expect(() => decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", ...PM })).toThrow(/Only owner may decide DEC-006; you are acting as project manager/);
    expect(() => decide(createSeedWorld(), { decisionId: "d-uat-signoff", action: "accept", ...OWNER })).toThrow(/Only customer approver may decide/);
    expect(() => decide(createSeedWorld(), { decisionId: "d-wi004", action: "accept", ...PM })).toThrow(DemoRuleError);
  });

  it("refuses to decide while the evidence is missing, but allows asking a question", () => {
    expect(() => decide(createSeedWorld(), { decisionId: "d-wi004", action: "accept", ...REVIEWER })).toThrow(/sandbox build and test run has not finished/);
    expect(() => decide(createSeedWorld(), { decisionId: "d-wi004", action: "reject", comment: "No", ...REVIEWER })).toThrow(/Cannot decide yet/);
    const asked = decide(createSeedWorld(), { decisionId: "d-wi004", action: "clarify", comment: "Which list sizes were tested?", ...REVIEWER });
    expect(byId(asked.decisions, "d-wi004")!.status).toBe("clarification_requested");
    expect(byId(asked.decisions, "d-wi004")!.outcome).toBeUndefined();
  });

  it("needs a comment to reject, ask or suggest, and refuses a decision already made", () => {
    expect(() => decide(createSeedWorld(), { decisionId: "d-platform", action: "reject", ...OWNER })).toThrow(/Add a comment/);
    expect(() => decide(createSeedWorld(), { decisionId: "d-tool", action: "accept", ...OWNER })).toThrow(/already modified/);
    const suggested = decide(createSeedWorld(), { decisionId: "d-platform", action: "comment", comment: "Check licence counts first", ...PM });
    expect(byId(suggested.decisions, "d-platform")!.status).toBe("pending");
    expect(byId(suggested.decisions, "d-platform")!.history.at(-1)!.summary).toBe("Suggested: Check licence counts first");
  });

  it("moving the cut-over mitigates the risk and takes the project out of critical", () => {
    const before = createSeedWorld();
    expect(projectHealth(before, byId(before.projects, "p-spo")!).health).toBe("critical");
    const after = decide(before, { decisionId: "d-cutover", action: "accept", ...OWNER });
    expect(byId(after.risks, "r1")!.status).toBe("mitigating");
    expect(projectHealth(after, byId(after.projects, "p-spo")!).health).toBe("at_risk"); // INC-003 and WI-008 still open
    expect(kpis(after).overdueDecisions).toBe(0);
    expect(invariantProblems(after)).toEqual([]);
  });

  it("the customer's UAT sign-off completes Phase 11", () => {
    const after = decide(createSeedWorld(), { decisionId: "d-uat-signoff", action: "accept", personId: "u-daniel", role: "customer_approver" });
    const project = byId(after.projects, "p-spse")!;
    expect(project.phases[10]).toMatchObject({ state: "completed", gateApprovedBy: "u-daniel" });
    expect(project.phases[11]!.state).toBe("active");
    expect(invariantProblems(after)).toEqual([]);
  });
});

describe("approvals", () => {
  const ready = () => advance(createSeedWorld(), 9); // WI-004's sandbox run has passed

  it("binds an approval to the exact version and sha256 approved", () => {
    const after = decide(ready(), { decisionId: "d-wi004", action: "accept", ...REVIEWER });
    const decision = byId(after.decisions, "d-wi004")!;
    const version = byId(after.artifacts, "doc-s-cs4")!.versions.at(-1)!;
    expect(decision.outcome!.boundTo).toEqual({ artifactId: "doc-s-cs4", version: 2, sha256: version.sha256 });
    expect(after.audit[0]!.detail).toContain(`bound to v2, sha256 ${version.sha256.slice(0, 12)}`);
    expect(invariantProblems(after)).toEqual([]);
  });

  it("choosing Request changes sends the work back to its agent instead of merging it", () => {
    const after = decide(ready(), { decisionId: "d-wi004", action: "choose_option", optionKey: "changes", comment: "Add a test for 1 million items", ...REVIEWER });
    expect(byId(after.decisions, "d-wi004")).toMatchObject({ status: "rejected", outcome: { action: "reject" } });
    expect(byId(after.tasks, "t-s4")!.state).toBe("changes_requested");
    expect(byId(after.artifacts, "doc-s-cs4")!.versions.at(-1)!.status).toBe("changes_requested");
    expect(byId(after.agents, "a-dev2")).toMatchObject({ status: "idle", taskId: undefined });
    expect(byId(after.decisions, "d-wi004")!.outcome!.boundTo).toBeUndefined();
    expect(invariantProblems(after)).toEqual([]);
  });

  it("cancels work that never started when its approval is rejected", () => {
    const after = decide(createSeedWorld(), { decisionId: "d-cr002", action: "reject", comment: "Keep the current design", ...OWNER });
    expect(byId(after.tasks, "t-p6")!.state).toBe("cancelled");
    expect(invariantProblems(after)).toEqual([]);
  });

  it("an approval cannot take a custom option", () => {
    expect(() => decide(ready(), { decisionId: "d-wi004", action: "custom", custom: "Merge half", ...REVIEWER })).toThrow(/approved or sent back/);
  });
});

describe("suggestions, deferral and questions", () => {
  it("anyone may suggest, but only the listed roles decide", () => {
    const suggested = decide(createSeedWorld(), { decisionId: "d-cutover", action: "comment", comment: "Tell the customer's finance team today", ...PM });
    expect(byId(suggested.decisions, "d-cutover")!.history.at(-1)).toMatchObject({ actor: "u-omar", action: "comment" });
    expect(() => decide(createSeedWorld(), { decisionId: "d-cutover", action: "comment", ...PM })).toThrow(/Write your suggestion/);
  });

  it("a deferred decision can be reopened by a decider, and is open again with no outcome", () => {
    const deferred = decide(createSeedWorld(), { decisionId: "d-platform", action: "defer", comment: "After the licence review", ...OWNER });
    expect(byId(deferred.decisions, "d-platform")!.status).toBe("deferred");
    expect(() => decide(deferred, { decisionId: "d-platform", action: "reopen", ...REVIEWER })).toThrow(/Only owner or project manager/);
    const reopened = decide(deferred, { decisionId: "d-platform", action: "reopen", ...OWNER });
    expect(byId(reopened.decisions, "d-platform")).toMatchObject({ status: "pending", outcome: undefined });
    expect(() => decide(createSeedWorld(), { decisionId: "d-platform", action: "reopen", ...OWNER })).toThrow(/Only a deferred decision/);
    expect(invariantProblems(reopened)).toEqual([]);
  });

  it("the agent answers a question two ticks later and the decision is open again", () => {
    const asked = decide(createSeedWorld(), { decisionId: "d-platform", action: "clarify", comment: "Which flows need premium connectors?", ...OWNER });
    expect(byId(advance(asked, 1).decisions, "d-platform")!.status).toBe("clarification_requested");
    const answered = advance(asked, 2);
    const decision = byId(answered.decisions, "d-platform")!;
    expect(decision.status).toBe("pending");
    expect(decision.history.at(-1)).toMatchObject({ actor: "a-ba", action: "answered" });
    expect(decision.history.at(-1)!.summary).toContain("3 flows");
    expect(answered.notifications[0]!.title).toBe("DEC-001 answered");
    expect(decision.recommended).toBe("spo");
    expect(invariantProblems(answered)).toEqual([]);
  });
});

describe("execution controls", () => {
  it("only owners and project managers control runs", () => {
    expect(() => controlExecution(createSeedWorld(), "x-101", "pause", "u-priya", "reviewer")).toThrow(/Only an owner or a project manager/);
  });

  it("pauses and resumes a running run", () => {
    const paused = controlExecution(createSeedWorld(), "x-101", "pause", "u-omar", "project_manager");
    expect(byId(paused.executions, "x-101")!.status).toBe("paused");
    expect(byId(paused.agents, "a-dev1")!.status).toBe("idle");
    expect(invariantProblems(paused)).toEqual([]);
    const resumed = controlExecution(paused, "x-101", "resume", "u-omar", "project_manager");
    expect(byId(resumed.executions, "x-101")!.status).toBe("running");
    expect(invariantProblems(resumed)).toEqual([]);
  });

  it("will not retry a run while its agent is busy, or retry a run that did not fail", () => {
    expect(() => controlExecution(createSeedWorld(), "x-107", "retry", "u-omar", "project_manager")).toThrow(/busy with "Implement WI-005/);
    expect(() => controlExecution(createSeedWorld(), "x-101", "retry", "u-omar", "project_manager")).toThrow(/A running run cannot be retried/);
    const retried = controlExecution(createSeedWorld(), "x-108", "retry", "u-omar", "project_manager");
    expect(byId(retried.executions, "x-108")).toMatchObject({ status: "retrying", attempt: 2 });
    expect(byId(retried.tasks, "t-i5")!.state).toBe("in_progress");
    expect(invariantProblems(retried)).toEqual([]);
  });
});
