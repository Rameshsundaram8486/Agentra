/* Documents with their versions, plus the starting activity feed, notifications and audit trail. */
import type { ActivityEvent, Artifact, ArtifactVersion, AuditEntry, Notification } from "@/types";
import { at, day } from "../time";

let shaCounter = 0;
function sha(): string {
  shaCounter += 1;
  // Deterministic, realistic-looking digests for the demo (not real hashes of real content).
  let value = (shaCounter * 2654435761) >>> 0;
  let out = "";
  for (let i = 0; i < 64; i++) {
    value = (Math.imul(value, 1103515245) + 12345) >>> 0; // 32-bit multiply; a plain * loses the low bits
    out += "0123456789abcdef"[(value >>> 16) & 15];
  }
  return out;
}

function version(no: number, when: string, author: string, summary: string, status: ArtifactVersion["status"], reviewedBy?: string): ArtifactVersion {
  return { no, at: when, author, summary, sha256: sha(), status, reviewedBy };
}

export const ARTIFACTS: Artifact[] = [
  { id: "doc-w-brd", projectId: "p-workflow", phase: 7, type: "brd", title: "Business requirements", ownerId: "u-sara", sourceAgentId: "a-ba", traces: ["OBJ-001", "REQ-F-001", "REQ-F-014"],
    excerpt: "Purchasing, leave and maintenance requests across 9 hotels move from paper and email to governed workflows with mobile approvals.",
    versions: [version(1, at(-2.5), "a-ba", "Drafted from the brief and interview notes; waiting on DEC-001", "draft")] },
  { id: "doc-w-notes", projectId: "p-workflow", phase: 7, type: "minutes", title: "Hotel operations interview notes", ownerId: "u-sara", traces: [],
    excerpt: "Duty managers approve purchase requests from their phones; general managers sign every PO today.",
    versions: [version(1, day(-4), "u-sara", "Notes from 9 hotel interviews", "approved", "u-sara")] },
  { id: "doc-p-sad", projectId: "p-power", phase: 8, type: "sad", title: "Solution design", ownerId: "u-omar", sourceAgentId: "a-sa", traces: ["REQ-F-001", "REQ-F-003", "CMP-001", "API-001"],
    excerpt: "Power Apps canvas app on Dataverse for referral intake; Power Automate for approvals and reminders; Entra ID groups for access.",
    versions: [version(1, day(-5), "a-sa", "First design: 39 items", "changes_requested", "u-priya"), version(2, at(-3.1), "a-sa", "Answers FND-1 to FND-4; 47 items", "in_review")] },
  { id: "doc-p-sec", projectId: "p-power", phase: 8, type: "security_review", title: "Security review", ownerId: "u-priya", sourceAgentId: "a-sec", traces: ["SC-01", "SC-03", "SC-08"],
    excerpt: "Review of design v1 found one high-severity gap (SC-03, encryption at rest); review of v2 in progress.",
    versions: [version(1, day(-4), "a-sec", "Review of design v1: SC-03 high", "approved", "u-priya")] },
  { id: "doc-s-brd", projectId: "p-spo", phase: 7, type: "brd", title: "Business requirements", ownerId: "u-omar", sourceAgentId: "a-ba", traces: ["REQ-F-001", "REQ-F-012", "REQ-N-004"],
    excerpt: "Migrate 42 site collections with permissions cleaned up, metadata preserved and no more than 4 hours of read-only time.",
    versions: [version(1, day(-40), "a-ba", "First draft", "changes_requested", "u-priya"), version(2, day(-36), "a-ba", "Answers 5 review comments", "changes_requested", "u-priya"), version(3, day(-30), "a-ba", "Baseline", "approved", "u-priya")] },
  { id: "doc-s-sad", projectId: "p-spo", phase: 8, type: "sad", title: "Migration architecture", ownerId: "u-omar", sourceAgentId: "a-sa", traces: ["CMP-001", "INT-002", "ENT-003"],
    excerpt: "Hub-and-spoke information architecture, SPMT for content, a throttling-aware scheduler and a staged cut-over.",
    versions: [version(1, day(-20), "a-sa", "First design", "changes_requested", "u-priya"), version(2, day(-14), "a-sa", "Adds the large-list handler; answers 3 findings", "approved", "u-priya")] },
  { id: "doc-s-hld", projectId: "p-spo", phase: 8, type: "hld", title: "High-level design", ownerId: "u-priya", sourceAgentId: "a-sa", traces: ["CMP-001", "CMP-002"],
    excerpt: "Target hubs, site templates, navigation and the migration pipeline.", versions: [version(1, day(-14), "a-sa", "From design v2", "approved", "u-priya")] },
  { id: "doc-s-lld", projectId: "p-spo", phase: 9, type: "lld", title: "Low-level design: migration pipeline", ownerId: "u-priya", sourceAgentId: "a-dev1", traces: ["WI-003", "WI-004", "WI-008"],
    excerpt: "Batch sizes, parallelism, back-off, logging and verification for each migration batch.", versions: [version(1, day(-9), "a-dev1", "Pipeline details", "approved", "u-priya")] },
  { id: "doc-s-cs4", projectId: "p-spo", phase: 9, type: "change_set", title: "Change set WI-004", ownerId: "u-priya", sourceAgentId: "a-dev2", traces: ["WI-004", "ENT-003", "REQ-N-004"],
    excerpt: "Large-list handler: pages through lists over 5,000 items in configurable batches; 2 new test files.",
    versions: [version(1, day(-2), "a-dev2", "First version", "changes_requested", "u-priya"), version(2, at(-1.2), "a-dev2", "Batch size configurable (REV-1)", "in_review")] },
  { id: "doc-s-runbook", projectId: "p-spo", phase: 9, type: "tech_spec", title: "Cut-over runbook (draft)", ownerId: "u-omar", sourceAgentId: "a-pm", traces: ["WI-007"],
    excerpt: "Freeze, final delta, DNS and navigation switch, verification and rollback steps.", versions: [version(1, day(-3), "a-pm", "Outline", "draft")] },
  { id: "doc-i-plan", projectId: "p-intranet", phase: 10, type: "test_plan", title: "Test plan", ownerId: "u-sara", sourceAgentId: "a-qa1", traces: ["REQ-F-001", "REQ-F-020", "REQ-N-002"],
    excerpt: "412 test cases in 8 suites: news, hubs, people search, permissions, accessibility, Teams app, performance and regression.",
    versions: [version(1, day(-12), "a-qa1", "First plan", "changes_requested", "u-priya"), version(2, day(-10), "a-qa1", "Adds permission and accessibility suites", "approved", "u-priya")] },
  { id: "doc-i-report", projectId: "p-intranet", phase: 10, type: "test_report", title: "Test report, run 2", ownerId: "u-sara", sourceAgentId: "a-qa1", traces: ["QA-06", "DEF-014"],
    excerpt: "396 of 412 passed; 1 critical (DEF-014), 3 major, 12 minor defects.", versions: [version(1, day(-2), "a-qa1", "Run 2 results", "in_review")] },
  { id: "doc-u-report", projectId: "p-spse", phase: 11, type: "uat_report", title: "UAT report", ownerId: "u-omar", sourceAgentId: "a-uat", traces: ["UAT-01", "UF-03", "UF-07"],
    excerpt: "35 of 36 scenarios passed; UF-03 fixed and retested; UF-07 proposed as a change request.", versions: [version(1, at(-4), "a-uat", "Round 1 results and feedback", "in_review")] },
  { id: "doc-u-signoff", projectId: "p-spse", phase: 11, type: "signoff", title: "UAT sign-off record", ownerId: "u-daniel", sourceAgentId: "a-uat", traces: ["UAT-RPT-v1"],
    excerpt: "Prepared for the customer approver; only the customer records sign-off.", versions: [version(1, at(-4), "a-uat", "Sign-off pack", "in_review")] },
  { id: "doc-c-minutes", projectId: "p-spo", phase: 9, type: "minutes", title: "Weekly status meeting, 24 November", ownerId: "u-omar", sourceAgentId: "a-voice", traces: [],
    excerpt: "Agreed to review the cut-over date after the WI-008 dry run. Recorded with consent of all attendees.", versions: [version(1, day(-2), "a-voice", "Minutes and actions", "approved", "u-omar")] },
  { id: "doc-c-report", projectId: "p-spo", phase: 9, type: "report", title: "Executive summary", ownerId: "u-rania", sourceAgentId: "a-rep", traces: [],
    excerpt: "Built from recorded workflow data only: status, decisions, blockers, risks and next actions.", versions: [version(13, day(-7), "a-rep", "Week 47", "approved", "u-rania"), version(14, at(-0.9), "a-rep", "Week 48", "draft")] },
  { id: "doc-d-proposal", projectId: "p-docai", phase: 3, type: "proposal", title: "Technical and commercial proposal (Preview)", ownerId: "u-rania", sourceAgentId: "a-prop", traces: [],
    excerpt: "Azure AI Document Intelligence with human review of low-confidence fields; fixed price AED 380,000.", versions: [version(1, day(-16), "a-prop", "Proposal", "approved", "u-rania")] },
];

export const ACTIVITY: ActivityEvent[] = [
  { id: "ev-12", at: at(-0.1), severity: "info", text: "Security Reviewer Agent started the security review of design v2", projectId: "p-power", agentId: "a-sec" },
  { id: "ev-11", at: at(-0.3), severity: "info", text: "Developer Agent started implementing WI-005 (managed metadata mapping)", projectId: "p-spo", agentId: "a-dev1" },
  { id: "ev-10", at: at(-0.7), severity: "info", text: "QA Agent started regression run 3 (412 test cases)", projectId: "p-intranet", agentId: "a-qa1" },
  { id: "ev-09", at: at(-0.9), severity: "success", text: "Reporting Agent generated the week 48 executive summary from records", agentId: "a-rep" },
  { id: "ev-08", at: at(-1.2), severity: "info", text: "Developer Agent 2 submitted change set WI-004 v2; sandbox build and tests queued", projectId: "p-spo", agentId: "a-dev2" },
  { id: "ev-07", at: at(-1.6), severity: "warning", text: "QA Agent 2: performance test timed out waiting for the load generator (INC-002)", projectId: "p-intranet", agentId: "a-qa2" },
  { id: "ev-06", at: at(-2.5), severity: "warning", text: "Business Analyst Agent needs a decision: target platform (DEC-001)", projectId: "p-workflow", agentId: "a-ba" },
  { id: "ev-05", at: at(-3), severity: "critical", text: "QA Agent detected critical defect DEF-014: search shows restricted HR documents", projectId: "p-intranet", agentId: "a-qa1" },
  { id: "ev-04", at: at(-3.1), severity: "success", text: "Solution Architect Agent submitted design v2, answering 4 security findings", projectId: "p-power", agentId: "a-sa" },
  { id: "ev-03", at: at(-4), severity: "info", text: "UAT & Release Agent prepared the sign-off pack for the customer approver", projectId: "p-spse", agentId: "a-uat" },
  { id: "ev-02", at: at(-4.9), severity: "critical", text: "Developer Agent: dry run of the batch scheduler failed after repeated throttling (INC-003)", projectId: "p-spo", agentId: "a-dev1" },
  { id: "ev-01", at: at(-26), severity: "warning", text: "Project Owner Agent identified a delay risk to the SharePoint Online cut-over (DEC-006)", projectId: "p-spo", agentId: "a-po" },
];

export const NOTIFICATIONS: Notification[] = [
  { id: "n-6", at: at(-1.2), title: "Change set ready for review", body: "WI-004 v2 is waiting for its sandbox run, then your approval.", severity: "info", read: false, link: "/decisions?id=d-wi004" },
  { id: "n-5", at: at(-1.6), title: "Incident INC-002 opened", body: "Performance test timed out on Enterprise Intranet Modernization.", severity: "warning", read: false, link: "/owner?tab=incidents" },
  { id: "n-4", at: at(-2.5), title: "Decision needed: target platform", body: "The Business Analyst Agent recommends SharePoint Online.", severity: "warning", read: false, link: "/decisions?id=d-platform" },
  { id: "n-3", at: at(-3), title: "Critical defect DEF-014", body: "Search shows restricted HR documents to some staff.", severity: "critical", read: false, link: "/decisions?id=d-def014" },
  { id: "n-2", at: at(-4), title: "UAT sign-off requested", body: "SharePoint Subscription Edition Upgrade is ready for the customer's sign-off.", severity: "info", read: true, link: "/decisions?id=d-uat-signoff" },
  { id: "n-1", at: at(-26), title: "Schedule change escalated", body: "The Project Owner Agent recommends moving the cut-over by one week.", severity: "critical", read: true, link: "/decisions?id=d-cutover" },
];

export const AUDIT: AuditEntry[] = [
  { id: "au-9", at: at(-1.2), actor: "a-dev2", action: "change_set.draft", target: "Change set WI-004 v2", detail: "5 files; sandbox run queued" },
  { id: "au-8", at: at(-1.6), actor: "system", action: "incident.open", target: "INC-002", detail: "From failed run x-108" },
  { id: "au-7", at: at(-2.6), actor: "a-ba", action: "decision.raise", target: "DEC-001", detail: "Target platform" },
  { id: "au-6", at: at(-3.1), actor: "a-sa", action: "artifact.version_add", target: "Solution design v2" },
  { id: "au-5", at: at(-4.9), actor: "system", action: "incident.open", target: "INC-003", detail: "From failed run x-107" },
  { id: "au-4", at: at(-20), actor: "u-omar", action: "change_request.raise", target: "CR-002", detail: "Design baseline; needs owner and reviewer" },
  { id: "au-3", at: at(-26), actor: "a-po", action: "decision.raise", target: "DEC-006", detail: "Escalation: cut-over date" },
  { id: "au-2", at: day(-5), actor: "u-rania", action: "decision.outcome", target: "DEC-012", detail: "Rejected" },
  { id: "au-1", at: day(-18), actor: "u-rania", action: "decision.outcome", target: "DEC-010", detail: "Something else: SPMT with a ShareGate trial" },
  { id: "au-10", at: day(-22), actor: "u-sara", action: "decision.outcome", target: "DEC-011", detail: "Deferred to phase 2" },
];
