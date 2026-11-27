/* Platform administration data: integrations, the model gateway, agent actions and their autonomy, and the policies
   the demo shows. Policies are transcribed from the backend's declarative files under config/ (named beside each one)
   so the demo shows Agentra's real rules. Everything about connections and usage is simulated; no credential, key or
   real tenant appears anywhere. */
import type { Autonomy, Integration, Role, Settings } from "@/types";
import { at } from "../time";

/* Integrations ---------------------------------------------------------------------------------------- */

export const INTEGRATIONS: Integration[] = [
  {
    id: "claude", name: "Claude API (Anthropic)", group: "Model providers", purpose: "Every agent's model calls, through the model gateway only.", status: "connected",
    auth: "API key in the secrets vault (never shown, never in prompts or logs)", authStatus: "Valid", scopes: ["messages"], syncs: false,
    config: [["Endpoint", "api.anthropic.com"], ["Default model", "claude-opus-5-5"], ["Monthly cap", "USD 50"]], lastCheckAt: at(-0.4),
  },
  {
    id: "m365", name: "Microsoft 365 (Entra ID)", group: "Microsoft 365", purpose: "Sign-in for people, and the directory of customer and staff accounts.", status: "connected",
    auth: "OAuth 2.0 app registration; client secret in the secrets vault", authStatus: "Valid until 14 May 2027", scopes: ["User.Read.All", "Group.Read.All"], syncs: true,
    config: [["Tenant", "agentra-demo.onmicrosoft.com (synthetic)"], ["Sign-in", "Single sign-on, MFA required"]], lastSyncAt: at(-1.1), lastCheckAt: at(-1.1),
  },
  {
    id: "spo", name: "SharePoint Online", group: "Microsoft 365", purpose: "Project document libraries: approved versions are published here.", status: "connected",
    auth: "Microsoft Graph, Sites.Selected (only the sites granted)", authStatus: "Valid", scopes: ["Sites.Selected"], syncs: true,
    config: [["Sites granted", "7 project sites"], ["Publishes", "Approved versions only"]], lastSyncAt: at(-0.6), lastCheckAt: at(-0.6),
  },
  {
    id: "teams", name: "Microsoft Teams", group: "Microsoft 365", purpose: "Notifications to project channels; approvals always open in Agentra.", status: "connected",
    auth: "Bot registration; secret in the secrets vault", authStatus: "Valid", scopes: ["ChannelMessage.Send"], syncs: false,
    config: [["Channels", "1 per project"], ["Sends", "Notifications only, never approvals"]], lastCheckAt: at(-2.2),
  },
  {
    id: "outlook", name: "Outlook", group: "Microsoft 365", purpose: "Email to staff; email to customers is drafted by agents and sent only after a person approves it.", status: "connected",
    auth: "Microsoft Graph, Mail.Send from one shared mailbox", authStatus: "Valid", scopes: ["Mail.Send"], syncs: false,
    config: [["Mailbox", "delivery@agentra-demo.example (synthetic)"], ["Customer email", "Needs a person's approval"]], lastCheckAt: at(-3.5),
  },
  {
    id: "azure", name: "Azure", group: "Engineering", purpose: "Customer Azure subscriptions for AI and integration projects.", status: "warning",
    auth: "Service principal with a certificate in the secrets vault", authStatus: "Certificate expires in 12 days", scopes: ["Reader", "Contributor on 2 resource groups"], syncs: true,
    config: [["Subscriptions", "2 (customer sandboxes)"], ["Production", "Not connected in the MVP"]], lastSyncAt: at(-5), lastCheckAt: at(-5),
    note: "Renew the certificate before 8 December; the Project Owner Agent will raise it as a risk 7 days before.",
  },
  {
    id: "github", name: "GitHub", group: "Engineering", purpose: "Mirror a project's repository to the customer's GitHub organization.", status: "not_connected",
    auth: "Not configured", authStatus: "None", scopes: [], syncs: false,
    config: [["Source of truth", "Agentra keeps each project's Git repository itself"]],
    note: "Agentra merges approved change sets into its own repository; a GitHub mirror is optional and not set up.",
  },
  {
    id: "ollama", name: "Ollama (local models)", group: "Model providers", purpose: "Run open models on Agentra's own hardware for data that must not leave the network.", status: "planned",
    auth: "Not applicable until configured", authStatus: "Planned", scopes: [], syncs: false, config: [["Status", "Planned; the MVP uses the Claude API only"]],
  },
  {
    id: "gpu", name: "Cloud GPU model endpoint", group: "Model providers", purpose: "A dedicated, self-hosted model endpoint for heavy or private workloads.", status: "planned",
    auth: "Not applicable until configured", authStatus: "Planned", scopes: [], syncs: false, config: [["Status", "Planned; the MVP uses the Claude API only"]],
  },
];

/* Model gateway --------------------------------------------------------------------------------------- */

/** Simulated gateway figures that the demo records cannot provide (latency and failures by hour). */
export const GATEWAY = {
  monthToDateUsd: 14.62, // spend before the runs recorded in the demo
  monthlyCapUsd: 50,
  defaults: { model: "claude-opus-5-5", effort: "medium", maxTokens: 16_000, timeoutSeconds: 240, maxRetries: 2, refusalFallback: true },
  latency: [ // hour label, p50 and p95 seconds of time to first token (simulated)
    ["00", 1.4, 3.1], ["02", 1.3, 2.9], ["04", 1.5, 3.4], ["06", 1.8, 4.6], ["08", 2.1, 5.2], ["10", 1.9, 4.8],
    ["12", 1.7, 4.1], ["14", 1.6, 3.8], ["16", 1.8, 4.3], ["18", 1.5, 3.5], ["20", 1.4, 3.2], ["22", 1.3, 3.0],
  ] as [string, number, number][],
  requests24h: 412,
  failures: [ // the gateway's error codes (config/policies/incident_rules.yaml)
    { at: at(-5.0), code: "rate_limited", agent: "a-dev1", detail: "HTTP 429; retried after 20 s and succeeded", retried: true },
    { at: at(-3.2), code: "provider_unavailable", agent: "a-qa1", detail: "Overloaded; retried once and succeeded", retried: true },
    { at: at(-1.9), code: "truncated", agent: "a-ba", detail: "Output reached max_tokens; re-run with the task's 64,000-token limit", retried: true },
    { at: at(-0.8), code: "guardrail_blocked", agent: "a-sa", detail: "Output cited a requirement ID that does not exist; nothing saved", retried: false },
  ],
};

export const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude API)", status: "Active", models: ["claude-opus-5-5 (all agents)", "Anthropic's recommended fallback (on refusal only)"] },
  { id: "ollama", name: "Ollama", status: "Planned", models: ["Open models, to be chosen"] },
  { id: "gpu", name: "Cloud GPU endpoint", status: "Planned", models: ["Self-hosted, to be chosen"] },
];

/** Token limits per agent from config/models.yaml (others use the defaults). */
export const MAX_TOKENS: Record<string, number> = { business_analyst: 24_000, solution_architect: 24_000 };

/* Autonomy -------------------------------------------------------------------------------------------- */

export const AUTONOMY_LEVELS: { level: Autonomy; name: string; definition: string; people: string; example: string }[] = [
  { level: "supervised", name: "Supervised", definition: "Prepares drafts and recommendations; a person reviews every consequential action.", people: "Review and approve each output before it is used.", example: "The Business Analyst Agent drafts the requirements; a reviewer approves the baseline." },
  { level: "controlled", name: "Controlled execution", definition: "Executes predefined low-risk actions within explicit permissions.", people: "Set the permissions; review the results and exceptions.", example: "The QA Agent runs the approved test suites in sandbox VMs and logs the defects it finds." },
  { level: "conditional", name: "Conditional autonomy", definition: "Executes approved workflows when the policy's preconditions are met.", people: "Approve the workflow and its preconditions once; handle escalations.", example: "The QA Agent retests a defect on its own once the fix is merged and its sandbox run passed." },
];

/** The highest autonomy an action of each risk class may have. */
export const MAX_FOR_RISK: Record<"low" | "medium" | "high", Autonomy> = { low: "conditional", medium: "controlled", high: "supervised" };

export const AUTONOMY_RANK: Record<Autonomy, number> = { supervised: 0, controlled: 1, conditional: 2 };

export interface AgentAction {
  key: string;
  title: string;
  risk: "low" | "medium" | "high";
  autonomy: Autonomy; // the default
  condition?: string; // what must hold for conditional autonomy
}

const A = (key: string, title: string, risk: AgentAction["risk"], autonomy: Autonomy, condition?: string): AgentAction => ({ key, title, risk, autonomy, condition });

export const AGENT_ACTIONS: Record<string, AgentAction[]> = {
  business_analyst: [A("draft_requirements", "Draft requirements and acceptance criteria", "low", "supervised"), A("raise_decision", "Raise a decision request for people", "low", "controlled"), A("send_customer_questions", "Send clarifying questions to the customer", "high", "supervised")],
  solution_architect: [A("draft_design", "Draft the solution design", "low", "supervised"), A("raise_decision", "Raise a design decision for people", "low", "controlled"), A("apply_design_change", "Apply an approved design change", "medium", "supervised")],
  security_reviewer: [A("review_design", "Review a design version against the security checklist", "low", "supervised"), A("record_findings", "Record findings on the review", "low", "controlled")],
  developer: [A("draft_change_set", "Draft a change set for a work item", "low", "supervised"), A("sandbox_build", "Build and test a change set in a sandbox VM", "medium", "controlled"), A("ask_questions", "Ask questions about a work item", "low", "controlled")],
  qa_tester: [A("draft_test_plan", "Draft the test plan", "low", "supervised"), A("run_suites", "Run approved test suites in sandbox VMs", "medium", "controlled"), A("log_defects", "Log defects from failed tests", "low", "controlled"), A("retest_fixes", "Retest a fixed defect", "low", "conditional", "The fix is merged and its change set passed its sandbox run")],
  uat_release: [A("prepare_scenarios", "Prepare UAT scenarios", "low", "supervised"), A("triage_feedback", "Triage customer feedback", "low", "supervised"), A("invite_testers", "Invite customer testers", "high", "supervised")],
  project_manager: [A("draft_status", "Draft status reports", "low", "supervised"), A("internal_updates", "Send status updates to Agentra's project managers", "low", "conditional", "Every figure comes from records and no decision is overdue"), A("forecast_milestones", "Update milestone forecasts", "medium", "controlled")],
  project_owner: [A("detect", "Detect risks and open incidents from failed runs", "low", "controlled"), A("draft_rca", "Draft root-cause analyses", "low", "supervised"), A("escalate", "Escalate to people", "low", "conditional", "A deadline passed, a critical defect is open, or a run failed twice")],
  reporting: [A("generate_reports", "Generate reports from records", "low", "controlled"), A("share_customer_reports", "Share customer-visible reports with the customer", "high", "supervised")],
};

/** An agent's actions: its own list, or a default pair for agents outside the MVP. */
export function actionsFor(typeKey: string, typeAutonomy: Autonomy): AgentAction[] {
  return AGENT_ACTIONS[typeKey] ?? [A("draft_outputs", "Draft outputs and recommendations", "low", typeAutonomy), A("external_contact", "Contact customers or external parties", "high", "supervised")];
}

/* Policies (from config/) ----------------------------------------------------------------------------- */

export const APPROVAL_MATRIX: { type: string; title: string; roles: Role[] }[] = [ // config/policies/approval_matrix.yaml
  { type: "requirements_baseline", title: "Requirements baseline", roles: ["reviewer", "owner"] },
  { type: "design_baseline", title: "Design baseline", roles: ["reviewer", "owner"] },
  { type: "security_review", title: "Security review", roles: ["reviewer"] },
  { type: "feasibility_review", title: "Feasibility review", roles: ["reviewer", "owner"] },
  { type: "implementation_backlog", title: "Implementation backlog", roles: ["owner", "project_manager", "reviewer"] },
  { type: "change_set", title: "Change set (after a passing sandbox run)", roles: ["reviewer"] },
  { type: "implementation_report", title: "Implementation report", roles: ["reviewer", "owner"] },
  { type: "qa_completion_report", title: "QA completion report", roles: ["reviewer", "owner"] },
  { type: "uat_signoff_record", title: "UAT sign-off record", roles: ["customer_approver"] },
];

export const PERMISSIONS: { key: string; label: string }[] = [ // config/policies/permissions.yaml
  { key: "project.view", label: "View projects" }, { key: "artifact.author", label: "Author documents" }, { key: "decision.raise", label: "Raise decisions" },
  { key: "agent.run", label: "Start agent tasks (paid model calls)" }, { key: "agent_run.view", label: "View agent runs, model and cost" }, { key: "change.raise", label: "Raise change requests" },
  { key: "report.generate", label: "Generate reports" }, { key: "report.view", label: "View all reports" }, { key: "report.view_customer", label: "View customer reports only" },
  { key: "incident.manage", label: "Investigate and resolve incidents" }, { key: "incident.close", label: "Verify and close incidents" }, { key: "audit.view", label: "View the audit log" },
];

export const ROLE_PERMISSIONS: Record<Role | "agent", string[]> = {
  owner: ["project.view", "artifact.author", "decision.raise", "agent.run", "agent_run.view", "change.raise", "report.generate", "report.view", "incident.manage", "incident.close", "audit.view"],
  project_manager: ["project.view", "artifact.author", "decision.raise", "agent.run", "agent_run.view", "change.raise", "report.generate", "report.view", "incident.manage", "audit.view"],
  reviewer: ["project.view", "agent_run.view", "report.view", "incident.close", "audit.view"],
  customer_approver: ["project.view", "report.view_customer"],
  agent: ["project.view", "artifact.author", "decision.raise"],
};

export const SEPARATION_OF_DUTIES = [ // config/policies/separation_of_duties.yaml and incident_rules.yaml
  "Only people approve or decide. Agent and system accounts never can, and this is not configurable.",
  "Anyone who authored any version of a document cannot approve, reject or request changes on it.",
  "An approval is valid only for the exact version and content sha256 it was given for; a newer version needs a new approval.",
  "The person who resolved an incident may not close it; someone else verifies it.",
];

export const CHANGE_SET_RULES = [ // config/policies/change_sets.yaml
  "At most 30 files, 200 KB per file and 1 MB in total per change set.",
  "Never changes pipeline definitions, git attributes, submodules or Agentra's own files.",
  "Build, integration and migration work must add or change at least one test.",
  "Each version is built and tested in a sandbox VM (15-minute limit) before a reviewer may approve it.",
];

export const NOTIFICATION_EVENTS = [
  { key: "decision_for_me", label: "A decision is waiting for my role" },
  { key: "decision_overdue", label: "A decision is overdue" },
  { key: "run_failed", label: "An agent run failed" },
  { key: "incident", label: "An incident is opened or changes status" },
  { key: "approval_done", label: "An approval I gave was applied (merged, baselined)" },
  { key: "briefing", label: "Daily Project Owner briefing" },
];
export const CHANNELS = [{ key: "app", label: "In Agentra" }, { key: "email", label: "Email (Outlook)" }, { key: "teams", label: "Teams" }];

export function defaultSettings(): Settings {
  const autonomy: Settings["autonomy"] = {};
  for (const [typeKey, actions] of Object.entries(AGENT_ACTIONS)) for (const a of actions) autonomy[`${typeKey}.${a.key}`] = a.autonomy;
  const notifications: Settings["notifications"] = {};
  for (const role of ["owner", "project_manager", "reviewer", "customer_approver"] as Role[]) {
    for (const e of NOTIFICATION_EVENTS) for (const c of CHANNELS) notifications[`${role}.${e.key}.${c.key}`] = c.key === "app" || (c.key === "email" && e.key !== "briefing" && e.key !== "run_failed");
  }
  return { autonomy, configVersions: { developer: 2 }, notifications };
}
