/* Phase content for the phase workspaces: requirements, design, development, QA and UAT details for the project in
   each MVP phase, and simple preview content for the phases outside the MVP. Statuses that change during the demo
   (a build passing, a baseline approved) are derived from the live records by the screens, not stored here. */

export type ReqKind = "objective" | "functional" | "non_functional" | "business_rule" | "assumption" | "dependency" | "open_question";

export interface RequirementItem {
  id: string;
  kind: ReqKind;
  title: string;
  status: "confirmed" | "proposed" | "open";
  priority?: "must" | "should" | "could";
  source: string;
  design?: string[];
  workItems?: string[];
  tests?: string[];
}

export interface RequirementsContent {
  stakeholders: { name: string; role: string; interest: string }[];
  items: RequirementItem[];
  baselineDoc: string; // artifact id whose latest version is the baseline
}

export const REQUIREMENTS: Record<string, RequirementsContent> = {
  "p-workflow": {
    baselineDoc: "doc-w-brd",
    stakeholders: [
      { name: "Group Operations Director", role: "Sponsor", interest: "One approval process across 9 hotels" },
      { name: "Hotel general managers", role: "Approvers", interest: "Approve spending at their property from a phone" },
      { name: "Group finance", role: "Approvers", interest: "Control of purchases above AED 10,000" },
      { name: "Duty managers", role: "Requesters", interest: "Raise maintenance and leave requests quickly" },
      { name: "Group IT", role: "Operators", interest: "No new servers; Microsoft 365 only" },
    ],
    items: [
      { id: "OBJ-001", kind: "objective", title: "Replace paper and email approvals in all 9 hotels within 3 months", status: "confirmed", source: "Brief v2" },
      { id: "OBJ-002", kind: "objective", title: "Cut purchase approval time from 4 days to 1 day", status: "confirmed", source: "Brief v2" },
      { id: "REQ-F-001", kind: "functional", title: "Duty managers raise purchase, leave and maintenance requests from a phone", status: "confirmed", priority: "must", source: "Interview notes" },
      { id: "REQ-F-002", kind: "functional", title: "Requests above AED 10,000 route to the general manager and group finance", status: "open", priority: "must", source: "DEC-002 (not answered)" },
      { id: "REQ-F-003", kind: "functional", title: "Approvers are reminded after one working day", status: "confirmed", priority: "should", source: "Interview notes" },
      { id: "REQ-F-004", kind: "functional", title: "Group finance sees every open purchase request across hotels", status: "confirmed", priority: "must", source: "Brief v2" },
      { id: "REQ-F-005", kind: "functional", title: "Maintenance requests carry photos and the room number", status: "proposed", priority: "could", source: "Agent suggestion" },
      { id: "REQ-N-001", kind: "non_functional", title: "Works on hotel Wi-Fi and mobile data; pages load in under 3 seconds", status: "confirmed", priority: "must", source: "Interview notes" },
      { id: "REQ-N-002", kind: "non_functional", title: "Arabic and English interfaces", status: "proposed", priority: "should", source: "Agent suggestion" },
      { id: "BR-001", kind: "business_rule", title: "Nobody approves their own request", status: "confirmed", source: "Group finance policy" },
      { id: "BR-002", kind: "business_rule", title: "Leave requests follow UAE labour law entitlements", status: "confirmed", source: "Brief v2" },
      { id: "ASM-001", kind: "assumption", title: "All hotels use the group's Microsoft 365 tenant", status: "proposed", source: "Brief v2" },
      { id: "DEP-001", kind: "dependency", title: "Premium connector licences for 3 flows", status: "open", source: "DEC-001 rationale" },
      { id: "OQ-001", kind: "open_question", title: "Target platform: SharePoint Online, Subscription Edition or hybrid?", status: "open", source: "DEC-001" },
      { id: "OQ-002", kind: "open_question", title: "Approval chain above AED 10,000", status: "open", source: "DEC-002" },
    ],
  },
  "p-spo": {
    baselineDoc: "doc-s-brd",
    stakeholders: [
      { name: "Head of IT, Al Noor Trading", role: "Sponsor", interest: "Retire the SharePoint 2016 farm before support ends" },
      { name: "Finance team", role: "Key users", interest: "No disruption at month-end close" },
    ],
    items: [
      { id: "REQ-F-001", kind: "functional", title: "Migrate 42 site collections with content, versions and metadata", status: "confirmed", priority: "must", source: "Brief", design: ["CMP-001", "INT-002"], workItems: ["WI-003", "WI-006"], tests: ["TC-014"] },
      { id: "REQ-F-012", kind: "functional", title: "Clean up broken and individual permissions before migration", status: "confirmed", priority: "must", source: "Discovery", design: ["SEC-001"], workItems: ["WI-002"], tests: ["TC-021"] },
      { id: "REQ-F-015", kind: "functional", title: "Lists over 5,000 items migrate without loss", status: "confirmed", priority: "must", source: "Discovery", design: ["ENT-003"], workItems: ["WI-004"], tests: ["TC-030"] },
      { id: "REQ-N-004", kind: "non_functional", title: "No more than 4 hours of read-only time per site at cut-over", status: "confirmed", priority: "must", source: "Brief", design: ["CMP-002"], workItems: ["WI-007", "WI-008"], tests: [] },
    ],
  },
};

export interface ArchitectureContent {
  designDoc: string;
  options: { key: string; title: string; score: number; chosen: boolean }[];
  layers: { name: string; items: { id: string; title: string }[] }[];
  integrations: { from: string; to: string; how: string }[];
  decisions: { id: string; title: string; status: "accepted" | "proposed" }[];
  security: { id: string; title: string; verdict: "met" | "gap"; severity?: "high" | "medium" | "low" }[];
}

export const ARCHITECTURE: Record<string, ArchitectureContent> = {
  "p-power": {
    designDoc: "doc-p-sad",
    options: [
      { key: "power_apps", title: "Power Apps with Dataverse", score: 4.3, chosen: true },
      { key: "custom_web", title: "Custom web app on Azure", score: 3.6, chosen: false },
      { key: "sharepoint_lists", title: "SharePoint lists and forms", score: 2.9, chosen: false },
    ],
    layers: [
      { name: "Experience", items: [{ id: "CMP-001", title: "Referral intake app (Power Apps)" }, { id: "CMP-002", title: "Clinician approvals in Teams" }] },
      { name: "Process", items: [{ id: "API-001", title: "Approval and reminder flows (Power Automate)" }, { id: "CMP-003", title: "Escalation rules" }] },
      { name: "Data", items: [{ id: "ENT-001", title: "Referral (Dataverse)" }, { id: "ENT-002", title: "Approval history" }] },
      { name: "Security", items: [{ id: "SEC-001", title: "Entra ID groups per clinic" }, { id: "SEC-002", title: "Dataverse encryption at rest" }] },
    ],
    integrations: [
      { from: "CMP-001", to: "ENT-001", how: "Dataverse connector" },
      { from: "API-001", to: "CMP-002", how: "Teams approvals" },
      { from: "API-001", to: "ENT-002", how: "Audit records" },
    ],
    decisions: [
      { id: "ADR-001", title: "Dataverse over SharePoint lists for patient-referral data", status: "accepted" },
      { id: "ADR-002", title: "Scheduled reminders instead of event triggers (CR-002)", status: "proposed" },
    ],
    security: [
      { id: "SC-01", title: "Access by role (Entra ID groups)", verdict: "met" },
      { id: "SC-03", title: "Encryption at rest", verdict: "met" },
      { id: "SC-06", title: "Data retention", verdict: "gap", severity: "medium" },
      { id: "SC-08", title: "Audit log retention beyond 90 days", verdict: "gap", severity: "medium" },
    ],
  },
};

export interface DevelopmentContent {
  tests: Record<string, [passed: number, total: number]>; // work item key -> unit tests in its latest build
}

export const DEVELOPMENT: Record<string, DevelopmentContent> = {
  "p-spo": { tests: { "WI-001": [22, 22], "WI-002": [31, 31], "WI-003": [14, 14], "WI-004": [48, 48], "WI-005": [61, 61], "WI-008": [17, 19] } },
};

export interface QaContent {
  suites: { name: string; cases: number; passed: number; failed: number; blocked: number }[];
  defects: { id: string; title: string; severity: "critical" | "major" | "minor"; status: "open" | "fixed" | "retested" | "deferred" }[];
  exitCriteria: { text: string; key: "no_critical" | "pass_rate" | "performance" | "accessibility" }[];
}

export const QA: Record<string, QaContent> = {
  "p-intranet": {
    suites: [
      { name: "News and announcements", cases: 64, passed: 64, failed: 0, blocked: 0 },
      { name: "Departmental hubs", cases: 58, passed: 58, failed: 0, blocked: 0 },
      { name: "People search", cases: 41, passed: 41, failed: 0, blocked: 0 },
      { name: "Permissions", cases: 18, passed: 15, failed: 3, blocked: 0 },
      { name: "Accessibility (WCAG 2.2 AA)", cases: 37, passed: 37, failed: 0, blocked: 0 },
      { name: "Teams app", cases: 44, passed: 42, failed: 2, blocked: 0 },
      { name: "Performance", cases: 6, passed: 0, failed: 0, blocked: 6 },
      { name: "Regression", cases: 144, passed: 141, failed: 3, blocked: 0 },
    ],
    defects: [
      { id: "DEF-014", title: "Search shows restricted HR documents to some staff", severity: "critical", status: "open" },
      { id: "DEF-016", title: "Teams app tab does not remember the last hub", severity: "major", status: "open" },
      { id: "DEF-011", title: "News web part paging skips items", severity: "major", status: "retested" },
      { id: "DEF-012", title: "Arabic text clipped in the mega menu", severity: "minor", status: "fixed" },
      { id: "DEF-019", title: "Hub logo blurry on high-resolution screens", severity: "minor", status: "deferred" },
    ],
    exitCriteria: [
      { text: "No open critical defects", key: "no_critical" },
      { text: "At least 98% of test cases passed", key: "pass_rate" },
      { text: "Performance test passed (500 users, p95 under 2.5 s)", key: "performance" },
      { text: "Accessibility audit passed", key: "accessibility" },
    ],
  },
};

export interface UatContent {
  scenarios: { group: string; total: number; passed: number; failed: number }[];
  feedback: { id: string; title: string; type: "defect" | "change_request" | "question"; status: "closed" | "open" | "proposed_cr" }[];
}

export const UAT: Record<string, UatContent> = {
  "p-spse": {
    scenarios: [
      { group: "Sites and navigation", total: 9, passed: 9, failed: 0 },
      { group: "Documents and versions", total: 10, passed: 10, failed: 0 },
      { group: "Search", total: 6, passed: 6, failed: 0 },
      { group: "Workflows and timer jobs", total: 7, passed: 7, failed: 0 },
      { group: "Reporting", total: 4, passed: 3, failed: 1 },
    ],
    feedback: [
      { id: "UF-03", title: "Timer job runs in the wrong time zone", type: "defect", status: "closed" },
      { id: "UF-05", title: "Where did the old 'My Sites' link go?", type: "question", status: "closed" },
      { id: "UF-07", title: "Monthly storage report per department", type: "change_request", status: "proposed_cr" },
      { id: "UF-09", title: "Search result previews slow on first load", type: "defect", status: "closed" },
      { id: "UF-11", title: "Recycle bin retention shorter than before", type: "question", status: "closed" },
    ],
  },
};

/* Previews: phases outside the MVP ------------------------------------------------------------------ */

export const PREVIEW: Record<number, { title: string; columns: string[]; rows: string[][]; note: string }> = {
  1: {
    title: "Leads", note: "Qualified by the Lead Generation Agent against the ideal customer profile; outreach drafts are sent by people.",
    columns: ["Lead", "Sector", "City", "Score", "Status"],
    rows: [["Crescent Marine Services", "Maritime", "Abu Dhabi", "82", "Qualified"], ["Palm Grove Schools", "Education", "Dubai", "76", "Qualified"], ["Silverline Clinics", "Healthcare", "Sharjah", "64", "Nurturing"], ["Atlas Freight Brokers", "Logistics", "Dubai", "58", "Nurturing"], ["Sandstone Realty", "Real estate", "Ajman", "41", "Not a fit"]],
  },
  2: {
    title: "Discovery meetings", note: "Notes are captured only with every attendee's recorded consent.",
    columns: ["Customer", "Meeting", "Date", "Consent", "Status"],
    rows: [["Crescent Marine Services", "Discovery: document management", "1 Dec", "Recorded", "Scheduled"], ["Palm Grove Schools", "Intranet walkthrough", "3 Dec", "Pending", "Proposed"], ["Oasis Ridge Healthcare", "AI document processing follow-up", "18 Nov", "Recorded", "Notes approved"]],
  },
  3: {
    title: "Proposals", note: "Drafted by the Proposal & Estimation Agent; nothing is sent without approval.",
    columns: ["Customer", "Proposal", "Value", "Version", "Status"],
    rows: [["Oasis Ridge Healthcare", "Azure AI Document Processing", "AED 380,000", "v3", "Accepted"], ["Crescent Marine Services", "SharePoint document management", "AED 210,000", "v1", "Draft, in review"]],
  },
  4: {
    title: "Negotiation", note: "Negotiated changes are recorded; people agree the commercial terms.",
    columns: ["Customer", "Item", "Requested", "Position", "Status"],
    rows: [["Oasis Ridge Healthcare", "Payment terms", "60 days", "45 days", "Agreed"], ["Oasis Ridge Healthcare", "Hypercare", "8 weeks", "6 weeks", "Agreed"]],
  },
  5: {
    title: "Award and purchase order", note: "The Commercial Control Agent checks the PO against the approved proposal; work starts only after it is validated.",
    columns: ["Project", "Check", "Expected", "Received", "Result"],
    rows: [["Azure AI Document Processing", "Purchase order", "AED 380,000", "Not received", "Waiting"], ["Azure AI Document Processing", "Award letter", "Signed", "Signed 14 Nov", "Valid"]],
  },
  6: {
    title: "Kickoff and governance", note: "The Project Manager Agent prepares the charter; people approve it.",
    columns: ["Project", "Item", "Owner", "Status"],
    rows: [["Enterprise Workflow Modernization", "Project charter", "Sara Khalil", "Approved"], ["Enterprise Workflow Modernization", "Weekly status meeting", "Project Manager Agent", "Set up"]],
  },
  12: {
    title: "Go-live readiness", note: "Production changes always need human approval; rollback steps are rehearsed first.",
    columns: ["Project", "Check", "Owner", "Status"],
    rows: [["SharePoint Subscription Edition Upgrade", "Customer UAT sign-off", "Daniel Weber", "Waiting"], ["SharePoint Subscription Edition Upgrade", "Rollback rehearsal", "Release & Deployment Agent", "Planned"], ["SharePoint Subscription Edition Upgrade", "Change advisory approval", "Rania Al Mansoori", "Not started"]],
  },
  13: {
    title: "Closure", note: "Lessons learned go to the knowledge base after people approve the closure report.",
    columns: ["Project", "Item", "Status"],
    rows: [["Employee Self-Service Portal", "Closure report", "Approved"], ["Employee Self-Service Portal", "Lessons learned published", "Done"]],
  },
};
