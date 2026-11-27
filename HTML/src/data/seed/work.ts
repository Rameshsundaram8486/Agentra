/* Agents (23 instances of the agent types), tasks and executions. An agent's status agrees with its task:
   working agents have a task in progress and a running execution; agents waiting for approval have a task
   waiting for review or input. The store's consistency tests check this. */
import type { Agent, Execution, LogLine, Task } from "@/types";
import { at, day } from "../time";

function agent(id: string, typeKey: string, name: string, status: Agent["status"], since: number, stats: [number, number, number], projectId?: string, taskId?: string): Agent {
  const [runs, failed, avgSeconds] = stats;
  return { id, typeKey, name, status, since: at(since), runs, succeeded: runs - failed, failed, avgSeconds, projectId, taskId };
}

export const AGENTS: Agent[] = [
  agent("a-ba", "business_analyst", "Business Analyst Agent", "waiting_approval", -2.5, [148, 4, 96], "p-workflow", "t-w2"),
  agent("a-sa", "solution_architect", "Solution Architect Agent", "waiting_approval", -3.1, [92, 3, 210], "p-power", "t-p2"),
  agent("a-sec", "security_reviewer", "Security Reviewer Agent", "working", -0.1, [61, 1, 140], "p-power", "t-p3"),
  agent("a-dev1", "developer", "Developer Agent", "working", -0.3, [233, 9, 380], "p-spo", "t-s5"),
  agent("a-dev2", "developer", "Developer Agent 2", "waiting_approval", -1.2, [187, 6, 395], "p-spo", "t-s4"),
  agent("a-qa1", "qa_tester", "QA Agent", "working", -0.7, [204, 5, 620], "p-intranet", "t-i1"),
  agent("a-qa2", "qa_tester", "QA Agent 2", "blocked", -1.6, [129, 7, 700], "p-intranet", "t-i5"),
  agent("a-uat", "uat_release", "UAT & Release Agent", "waiting_approval", -4.0, [77, 1, 160], "p-spse", "t-u5"),
  agent("a-rel", "release_deployment", "Release & Deployment Agent", "idle", -20, [38, 0, 240]),
  agent("a-pm", "project_manager", "Project Manager Agent", "working", -0.05, [512, 6, 45]),
  agent("a-po", "project_owner", "Project Owner Agent", "working", -0.02, [1046, 3, 70]),
  agent("a-orch", "company_orchestrator", "Company Orchestrator Agent", "working", -0.01, [2210, 11, 8]),
  agent("a-know", "knowledge_operations", "Knowledge Operations Agent", "idle", -6, [143, 2, 120]),
  agent("a-rep", "reporting", "Reporting Agent", "completed", -0.9, [388, 2, 55]),
  agent("a-cs", "customer_success", "Customer Success Agent", "idle", -9, [96, 0, 80]),
  agent("a-lead", "sales_lead_generation", "Lead Generation Agent", "working", -0.4, [310, 8, 150]),
  agent("a-mkt", "market_research", "Market Research Agent", "idle", -14, [121, 1, 260]),
  agent("a-disc", "opportunity_discovery", "Opportunity & Discovery Agent", "idle", -26, [58, 1, 300]),
  agent("a-sched", "scheduling", "Scheduling Agent", "idle", -3, [201, 0, 12]),
  agent("a-voice", "voice_meeting", "Meeting Assistant Agent", "idle", -27, [47, 0, 420]),
  agent("a-prop", "proposal_estimation", "Proposal & Estimation Agent", "completed", -5, [64, 2, 540]),
  agent("a-pres", "presentation", "Presentation Agent", "idle", -48, [29, 0, 330]),
  agent("a-comm", "commercial_control", "Commercial Control Agent", "blocked", -22, [51, 0, 90], "p-docai", "t-d1"),
];

type TaskSeed = [id: string, key: string, projectId: string, phase: number, title: string, state: Task["state"], priority: Task["priority"], agentId: string | undefined, hours: number, dependsOn: string[], createdDays: number];

const TASK_SEEDS: TaskSeed[] = [
  // Enterprise Workflow Modernization - Phase 7
  ["t-w1", "BA-01", "p-workflow", 7, "Clarify the project brief", "completed", "high", "a-ba", 6, [], -5],
  ["t-w2", "BA-02", "p-workflow", 7, "Draft the requirements baseline", "waiting_for_input", "high", "a-ba", 16, ["t-w1"], -4],
  ["t-w3", "BA-03", "p-workflow", 7, "Capture hotel operations interview notes", "completed", "medium", undefined, 8, [], -5],
  ["t-w4", "BA-04", "p-workflow", 7, "Build the requirements traceability matrix", "not_started", "medium", "a-ba", 6, ["t-w2"], -4],
  ["t-w5", "BA-05", "p-workflow", 7, "Review and baseline the requirements", "not_started", "high", undefined, 4, ["t-w2", "t-w4"], -4],
  // Power Platform Automation - Phase 8
  ["t-p1", "SA-01", "p-power", 8, "Compare solution options", "completed", "high", "a-sa", 8, [], -8],
  ["t-p2", "SA-02", "p-power", 8, "Draft and review the solution design", "waiting_for_review", "high", "a-sa", 20, ["t-p1"], -7],
  ["t-p3", "SA-03", "p-power", 8, "Security review of design v2", "in_progress", "high", "a-sec", 6, ["t-p1"], -2],
  ["t-p4", "SA-04", "p-power", 8, "Feasibility review of design v2", "completed", "medium", "a-dev1", 5, ["t-p1"], -2],
  ["t-p5", "SA-05", "p-power", 8, "Plan the implementation backlog", "not_started", "medium", undefined, 8, ["t-p2"], -7],
  ["t-p6", "CR-002", "p-power", 8, "Apply design change CR-002 (scheduled reminders)", "not_started", "medium", "a-sa", 4, [], -1],
  // SharePoint Online Migration - Phase 9 work items
  ["t-s1", "WI-001", "p-spo", 9, "Provision target site collections and hubs", "completed", "high", "a-dev1", 16, [], -12],
  ["t-s2", "WI-002", "p-spo", 9, "Permission mapping and clean-up scripts", "completed", "high", "a-dev2", 24, [], -12],
  ["t-s3", "WI-003", "p-spo", 9, "Migration batch plan for 42 site collections", "completed", "medium", "a-dev1", 12, ["t-s1"], -11],
  ["t-s4", "WI-004", "p-spo", 9, "Large-list migration handler (lists over 5,000 items)", "waiting_for_review", "high", "a-dev2", 20, ["t-s3"], -8],
  ["t-s5", "WI-005", "p-spo", 9, "Managed metadata and term store mapping", "in_progress", "medium", "a-dev1", 14, ["t-s3"], -7],
  ["t-s6", "WI-006", "p-spo", 9, "Pilot migration of 3 site collections", "not_started", "high", undefined, 18, ["t-s4", "t-s5"], -7],
  ["t-s7", "WI-007", "p-spo", 9, "Cut-over runbook and rollback plan", "not_started", "high", undefined, 10, ["t-s6"], -7],
  ["t-s8", "WI-008", "p-spo", 9, "Throttling-aware batch scheduler", "failed", "critical", "a-dev1", 12, ["t-s3"], -5],
  // Enterprise Intranet Modernization - Phase 10
  ["t-i1", "QA-07", "p-intranet", 10, "Regression suite, run 3 (412 test cases)", "in_progress", "high", "a-qa1", 10, [], -2],
  ["t-i2", "QA-04", "p-intranet", 10, "Retest DEF-011 (news web part paging)", "completed", "medium", "a-qa1", 2, [], -4],
  ["t-i3", "QA-05", "p-intranet", 10, "Accessibility audit (WCAG 2.2 AA)", "completed", "high", "a-qa2", 8, [], -6],
  ["t-i4", "QA-06", "p-intranet", 10, "Search permission-trimming tests", "completed", "critical", "a-qa1", 6, [], -3],
  ["t-i5", "QA-08", "p-intranet", 10, "Performance test: 500 concurrent users", "blocked", "high", "a-qa2", 8, [], -2],
  ["t-i6", "DEF-014", "p-intranet", 10, "Fix DEF-014: search shows restricted HR documents", "not_started", "critical", undefined, 6, ["t-i4"], -1],
  ["t-i7", "QA-09", "p-intranet", 10, "QA completion report", "not_started", "high", "a-qa1", 4, ["t-i1", "t-i5", "t-i6"], -2],
  // SharePoint Subscription Edition Upgrade - Phase 11
  ["t-u1", "UAT-01", "p-spse", 11, "Prepare UAT scenario pack (36 scenarios)", "completed", "high", "a-uat", 8, [], -8],
  ["t-u2", "UAT-02", "p-spse", 11, "Support UAT round 1", "completed", "high", "a-uat", 16, ["t-u1"], -6],
  ["t-u3", "UAT-03", "p-spse", 11, "Triage UAT feedback (12 items)", "completed", "medium", "a-uat", 4, ["t-u2"], -4],
  ["t-u4", "UF-03", "p-spse", 11, "Fix UF-03: timer job runs in the wrong time zone", "completed", "medium", "a-dev2", 3, ["t-u3"], -3],
  ["t-u5", "UAT-05", "p-spse", 11, "Prepare the sign-off pack", "waiting_for_review", "high", "a-uat", 3, ["t-u3", "t-u4"], -2],
  ["t-u6", "GL-01", "p-spse", 12, "Go-live readiness checklist", "not_started", "high", "a-rel", 4, ["t-u5"], -2],
  // Azure AI Document Processing - Phase 5 (on hold)
  ["t-d1", "AW-01", "p-docai", 5, "Validate purchase order against the approved proposal", "blocked", "high", "a-comm", 2, [], -9],
  ["t-d2", "AW-02", "p-docai", 6, "Prepare kickoff pack", "not_started", "medium", "a-pm", 6, ["t-d1"], -9],
  // Employee Self-Service Portal - completed
  ["t-e1", "CL-01", "p-ess", 13, "Closure report and lessons learned", "completed", "medium", "a-pm", 6, [], -45],
  ["t-e2", "CL-02", "p-ess", 13, "Publish lessons learned to the knowledge base", "completed", "low", "a-know", 2, ["t-e1"], -44],
];

export const TASKS: Task[] = TASK_SEEDS.map(([id, key, projectId, phase, title, state, priority, agentId, estimateHours, dependsOn, createdDays]) => {
  const started = ["in_progress", "waiting_for_input", "waiting_for_review", "changes_requested", "blocked", "failed", "completed"].includes(state);
  return {
    id, key, projectId, phase, title, state, priority, agentId, estimateHours, dependsOn,
    createdAt: day(createdDays),
    startedAt: started ? day(createdDays + 1) : undefined,
    completedAt: state === "completed" ? day(createdDays + 2) : undefined,
    due: day(createdDays + 10),
  };
});

function logs(startHours: number, lines: [number, LogLine["level"], string][]): LogLine[] {
  return lines.map(([minutes, level, text]) => ({ at: at(startHours + minutes / 60), level, text }));
}

type ExecutionSeed = Omit<Execution, "attempt" | "maxAttempts"> & { attempt?: number; maxAttempts?: number };

function execution(seed: ExecutionSeed): Execution {
  return { attempt: 1, maxAttempts: 2, ...seed };
}

export const EXECUTIONS: Execution[] = [
  execution({
    id: "x-101", agentId: "a-dev1", projectId: "p-spo", taskId: "t-s5", title: "Implement WI-005: managed metadata mapping", status: "running", startedAt: at(-0.3),
    input: "Work item WI-005, design items ENT-003 and INT-002, term store export (2,140 terms), main at 7f3c1a2", tokensIn: 41_200, tokensOut: 9_800, costUsd: 0.36, handoffTo: "qa_tester",
    logs: logs(-0.3, [[0, "info", "Run started: implement_work_item for WI-005"], [1, "info", "Read 6 repository files and the term store export"], [6, "info", "Mapping 2,140 terms to 9 term sets"], [12, "info", "Writing tests for 14 mapping rules"]]),
  }),
  execution({
    id: "x-102", agentId: "a-qa1", projectId: "p-intranet", taskId: "t-i1", title: "Regression suite, run 3", status: "running", startedAt: at(-0.7),
    input: "Test plan v2 (412 cases), build 1.9.3, test tenant", tokensIn: 18_300, tokensOut: 4_100, costUsd: 0.15, handoffTo: "uat_release",
    logs: logs(-0.7, [[0, "info", "Sandbox VM win-test-03 ready"], [3, "info", "Running 412 test cases in 8 suites"], [21, "info", "Suites 1-4 passed (204 of 204)"], [38, "warn", "Suite 5: 2 cases slower than threshold"]]),
  }),
  execution({
    id: "x-103", agentId: "a-sec", projectId: "p-power", taskId: "t-p3", title: "Security review of design v2", status: "running", startedAt: at(-0.1),
    input: "Solution design v2 (47 items), security checklist v3 (SC-01 to SC-10)", tokensIn: 26_900, tokensOut: 2_300, costUsd: 0.13, handoffTo: "solution_architect",
    logs: logs(-0.1, [[0, "info", "Run started: review_security"], [2, "info", "Checking SC-01 to SC-10 against 47 design items"]]),
  }),
  execution({
    id: "x-104", agentId: "a-po", title: "Portfolio health scan", status: "running", startedAt: at(-0.02),
    input: "6 active projects, 36 tasks, 12 decisions, 6 risks, 3 incidents", tokensIn: 52_000, tokensOut: 1_200, costUsd: 0.23,
    logs: logs(-0.02, [[0, "info", "Scanning projects for delays, stuck work and overdue decisions"]]),
  }),
  execution({
    id: "x-105", agentId: "a-dev2", projectId: "p-spo", taskId: "t-s4", title: "Implement WI-004 v2: large-list handler", status: "succeeded", startedAt: at(-1.4), endedAt: at(-1.2),
    input: "Work item WI-004, review comment REV-1 (batch size), main at 7f3c1a2", output: "Change set WI-004 v2: 5 files, 2 test files; queued for a sandbox build and test run", tokensIn: 38_100, tokensOut: 11_400, costUsd: 0.38, handoffTo: "qa_tester",
    logs: logs(-1.4, [[0, "info", "Run started: implement_work_item for WI-004"], [4, "info", "Answering review comment REV-1: batch size now configurable"], [11, "info", "Change set checks passed (paths, sizes, secrets, tests)"], [12, "info", "Committed to wi/WI-004/v2; sandbox run queued"]]),
  }),
  execution({
    id: "x-106", agentId: "a-sa", projectId: "p-power", taskId: "t-p2", title: "Draft solution design v2", status: "succeeded", startedAt: at(-3.4), endedAt: at(-3.1),
    input: "Requirements baseline v2, chosen option: Power Apps with Dataverse, 4 security findings to answer", output: "Design v2: 47 items, every confirmed requirement covered, 4 findings answered", tokensIn: 61_000, tokensOut: 22_800, costUsd: 0.70, handoffTo: "security_reviewer",
    logs: logs(-3.4, [[0, "info", "Run started: draft_design"], [9, "info", "Answered FND-1 to FND-4"], [17, "info", "Coverage: 31 of 31 confirmed requirements"]]),
  }),
  execution({
    id: "x-107", agentId: "a-dev1", projectId: "p-spo", taskId: "t-s8", title: "Dry run: throttling-aware batch scheduler", status: "failed", startedAt: at(-5.2), endedAt: at(-4.9), attempt: 2,
    input: "Work item WI-008, batch 3 (6 site collections, 212 GB)", output: "Stopped after repeated HTTP 429 responses from the SharePoint Online test tenant", tokensIn: 22_000, tokensOut: 3_900, costUsd: 0.17,
    logs: logs(-5.2, [[0, "info", "Dry run started on test tenant"], [9, "warn", "HTTP 429 Too Many Requests (Retry-After 120s)"], [14, "warn", "HTTP 429 again after back-off"], [18, "error", "Run failed after 2 attempts; incident INC-003 opened"]]),
  }),
  execution({
    id: "x-108", agentId: "a-qa2", projectId: "p-intranet", taskId: "t-i5", title: "Performance test: 500 concurrent users", status: "failed", startedAt: at(-1.9), endedAt: at(-1.6),
    input: "Load profile v1, test tenant, 500 virtual users", output: "Load generator VM did not report back within 15 minutes", tokensIn: 8_200, tokensOut: 1_100, costUsd: 0.05,
    logs: logs(-1.9, [[0, "info", "Provisioning load generator VM"], [15, "error", "Timed out waiting for the load generator; incident INC-002 opened"]]),
  }),
  execution({
    id: "x-109", agentId: "a-uat", projectId: "p-spse", taskId: "t-u5", title: "Prepare the UAT sign-off pack", status: "succeeded", startedAt: at(-4.3), endedAt: at(-4.0),
    input: "36 UAT scenarios, 12 feedback items (11 closed, 1 proposed as a change request)", output: "Sign-off pack v1 for the customer approver; sign-off is recorded only by the customer", tokensIn: 19_400, tokensOut: 6_200, costUsd: 0.20, handoffTo: "release_deployment",
    logs: logs(-4.3, [[0, "info", "Compiling UAT results"], [12, "info", "Sign-off pack ready for review"]]),
  }),
  execution({
    id: "x-110", agentId: "a-ba", projectId: "p-workflow", taskId: "t-w2", title: "Draft requirements v1", status: "succeeded", startedAt: at(-2.8), endedAt: at(-2.5),
    input: "Brief, interview notes (9 hotels), 3 answered questions", output: "Paused for a decision: the target platform (DEC-001) shapes 14 requirements", tokensIn: 33_000, tokensOut: 7_700, costUsd: 0.29, handoffTo: "solution_architect",
    logs: logs(-2.8, [[0, "info", "Run started: draft_requirements"], [14, "info", "Raised DEC-001: target platform"], [17, "info", "Task waiting for input"]]),
  }),
  execution({
    id: "x-111", agentId: "a-rep", title: "Weekly executive report", status: "succeeded", startedAt: at(-1.0), endedAt: at(-0.9),
    input: "Recorded workflow data for 7 projects", output: "Executive summary v14 generated from records", tokensIn: 24_000, tokensOut: 3_300, costUsd: 0.16,
    logs: logs(-1.0, [[0, "info", "Collecting records"], [5, "info", "Report v14 rendered"]]),
  }),
  execution({
    id: "x-112", agentId: "a-lead", title: "Qualify 12 inbound leads (Preview)", status: "running", startedAt: at(-0.4),
    input: "12 inbound enquiries, ideal customer profile v2", tokensIn: 14_000, tokensOut: 2_000, costUsd: 0.09,
    logs: logs(-0.4, [[0, "info", "Scoring leads against the ideal customer profile"]]),
  }),
  execution({
    id: "x-113", agentId: "a-dev2", projectId: "p-spo", taskId: "t-s2", title: "Implement WI-002: permission clean-up scripts", status: "failed", startedAt: at(-30), endedAt: at(-29.8),
    input: "Work item WI-002", output: "Refused by the change set checks: modified a file that does not exist on main", tokensIn: 30_000, tokensOut: 8_000, costUsd: 0.28,
    logs: logs(-30, [[0, "info", "Run started"], [10, "error", "Change set check failed: scripts/permissions.ps1 does not exist on main; nothing was saved"]]),
  }),
];

// A run in flight counts as a run without an outcome yet.
for (const execution of EXECUTIONS) {
  if (execution.status !== "running") continue;
  const owner = AGENTS.find((a) => a.id === execution.agentId)!;
  owner.succeeded -= 1;
}
