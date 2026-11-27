/* Domain types of the Command Center demo. They follow the real Agentra model (phases, workflow task states,
   decisions with options and outcomes, approvals bound to a role) so an API-backed DataService can fill them later.
   Values marked "derived" are never stored: selectors compute them from the records (store/selectors.ts). */

export type ISODate = string;

export type Role = "owner" | "project_manager" | "reviewer" | "customer_approver";
export type Autonomy = "supervised" | "controlled" | "conditional";
export type Priority = "critical" | "high" | "medium" | "low";
export type Severity = "info" | "success" | "warning" | "critical";

export type ServiceLine = "sharepoint_migration" | "intranet" | "power_platform" | "azure" | "ai" | "automation";

export interface Customer {
  id: string;
  name: string;
  sector: string;
  city: string;
  country: string;
}

export interface Person {
  id: string;
  name: string;
  title: string;
  role: Role;
  customerId?: string; // customer approvers work for a customer
}

/* Lifecycle ------------------------------------------------------------------------------------------- */

export interface PhaseDefinition {
  number: number;
  key: string;
  name: string;
  short: string;
  mvp: boolean; // Phases 7-11 are the MVP; the rest are previews
  primaryAgent: string; // agent type key
  gate: string; // what must be approved to leave the phase
  gateRoles: Role[];
  description: string;
}

export type PhaseState = "completed" | "active" | "awaiting_approval" | "blocked" | "upcoming";

export interface ProjectPhase {
  phase: number;
  state: PhaseState;
  progress: number; // 0-100, for active phases
  startedAt?: ISODate;
  completedAt?: ISODate;
  gateApprovedBy?: string; // person id
}

export interface Milestone {
  id: string;
  title: string;
  phase: number;
  due: ISODate;
  done: boolean;
}

export type ProjectStatus = "active" | "on_hold" | "completed";
export type Health = "on_track" | "at_risk" | "critical" | "on_hold" | "completed"; // derived

export interface Project {
  id: string;
  code: string;
  name: string;
  customerId: string;
  service: ServiceLine;
  status: ProjectStatus;
  managerId: string; // person id
  summary: string;
  startDate: ISODate;
  targetDate: ISODate;
  budgetAed: number;
  spentAed: number;
  phases: ProjectPhase[]; // all 13
  milestones: Milestone[];
  holdReason?: string;
}

/* Agents --------------------------------------------------------------------------------------------- */

export type AgentCategory = "sales" | "business_analysis" | "architecture" | "development" | "qa" | "project_management" | "governance" | "reporting";

export interface AgentType {
  key: string;
  name: string;
  category: AgentCategory;
  description: string;
  phases: number[];
  model: string;
  effort: "low" | "medium" | "high" | "xhigh";
  tools: string[];
  autonomy: Autonomy;
  inMvp: boolean;
}

export type AgentStatus = "working" | "idle" | "waiting_approval" | "blocked" | "failed" | "completed";

export interface Agent {
  id: string;
  typeKey: string;
  name: string;
  status: AgentStatus;
  projectId?: string;
  taskId?: string;
  since: ISODate; // when it entered this status
  runs: number;
  succeeded: number;
  failed: number;
  avgSeconds: number;
}

/* Work ----------------------------------------------------------------------------------------------- */

export type TaskState =
  | "not_started"
  | "ready"
  | "in_progress"
  | "waiting_for_input"
  | "waiting_for_review"
  | "changes_requested"
  | "blocked"
  | "failed"
  | "completed"
  | "cancelled";

export interface Task {
  id: string;
  key: string; // e.g. WI-004, TC-012, REQ task
  projectId: string;
  phase: number;
  title: string;
  agentId?: string;
  state: TaskState;
  priority: Priority;
  estimateHours: number;
  dependsOn: string[];
  createdAt: ISODate;
  startedAt?: ISODate;
  completedAt?: ISODate;
  due?: ISODate;
}

export type ExecutionStatus = "queued" | "running" | "paused" | "retrying" | "succeeded" | "failed";

export interface LogLine {
  at: ISODate;
  level: "info" | "warn" | "error";
  text: string;
}

export interface Execution {
  id: string;
  agentId: string;
  projectId?: string; // none for company-wide work (portfolio scans, reports, lead generation)
  taskId?: string;
  title: string;
  status: ExecutionStatus;
  startedAt: ISODate;
  endedAt?: ISODate;
  attempt: number;
  maxAttempts: number;
  input: string;
  output?: string;
  tokensIn: number;
  tokensOut: number;
  costUsd: number;
  logs: LogLine[];
  handoffTo?: string; // agent type key the output goes to next
  finishAt?: number; // simulation only: the elapsed tick at which a retried run finishes
}

/* Governance ----------------------------------------------------------------------------------------- */

export type DecisionKind = "approval" | "recommendation" | "escalation" | "question";
export type DecisionStatus = "pending" | "approved" | "modified" | "rejected" | "deferred" | "clarification_requested";
export type DecisionAction = "accept" | "choose_option" | "custom" | "reject" | "defer" | "clarify" | "comment" | "reopen";

export interface DecisionOption {
  key: string;
  title: string;
  description: string;
  pros: string[];
  cons: string[];
}

export interface DecisionEvent {
  at: ISODate;
  actor: string; // person id or agent id
  action: DecisionAction | "raised" | "answered";
  summary: string;
}

export interface DecisionOutcome {
  action: DecisionAction;
  optionKey?: string;
  custom?: string;
  comment?: string;
  constraints?: string;
  by: string; // person id
  at: ISODate;
  boundTo?: { artifactId: string; version: number; sha256: string }; // an approval binds to the exact version approved
}

export interface Decision {
  id: string;
  code: string; // DEC-012
  projectId: string;
  phase: number;
  kind: DecisionKind;
  title: string;
  question: string;
  originAgentId: string;
  priority: Priority;
  allowedRoles: Role[];
  createdAt: ISODate;
  deadline: ISODate;
  options: DecisionOption[];
  recommended?: string; // option key, preserved exactly as raised
  rationale: string;
  risks: string[];
  evidence: { label: string; ref: string }[];
  blockedBy?: string; // why it cannot be decided yet (e.g. tests not passed)
  taskId?: string; // approvals: the work item waiting for this decision
  artifactId?: string; // approvals: the document or change set being approved
  status: DecisionStatus;
  outcome?: DecisionOutcome;
  history: DecisionEvent[];
}

export type RiskStatus = "open" | "mitigating" | "closed";

export interface Risk {
  id: string;
  code: string;
  projectId: string;
  title: string;
  category: "schedule" | "technical" | "security" | "commercial" | "resourcing";
  likelihood: 1 | 2 | 3 | 4 | 5;
  impact: 1 | 2 | 3 | 4 | 5;
  status: RiskStatus;
  ownerId: string;
  mitigation: string;
  detectedBy: string; // agent id
  detectedAt: ISODate;
}

export type IncidentStatus = "open" | "investigating" | "resolved" | "closed";

export interface RootCause {
  whatHappened: string;
  facts: string[]; // observed, recorded evidence
  hypothesis: string; // the AI's probable cause, never presented as fact
  confidence: "low" | "medium" | "high";
  businessImpact: string;
  containment: string;
  correctiveAction: string;
  ownerId: string;
  verification: string;
}

export interface Incident {
  id: string;
  code: string;
  projectId: string;
  agentId: string;
  executionId?: string;
  title: string;
  severity: Priority;
  status: IncidentStatus;
  occurredAt: ISODate;
  rca: RootCause;
}

/* Documents ------------------------------------------------------------------------------------------ */

export type ArtifactType =
  | "brd"
  | "sad"
  | "hld"
  | "lld"
  | "tech_spec"
  | "security_review"
  | "backlog"
  | "change_set"
  | "test_plan"
  | "test_report"
  | "uat_report"
  | "signoff"
  | "minutes"
  | "report"
  | "proposal";

export type ArtifactStatus = "draft" | "in_review" | "changes_requested" | "approved";

export interface ArtifactVersion {
  no: number;
  at: ISODate;
  author: string; // agent id or person id
  summary: string;
  sha256: string;
  status: ArtifactStatus;
  reviewedBy?: string;
}

export interface Artifact {
  id: string;
  projectId: string;
  phase: number;
  type: ArtifactType;
  title: string;
  ownerId: string; // responsible person
  sourceAgentId?: string;
  versions: ArtifactVersion[]; // oldest first
  traces: string[]; // requirement / design item IDs
  excerpt: string;
}

/* Activity -------------------------------------------------------------------------------------------- */

export interface ActivityEvent {
  id: string;
  at: ISODate;
  severity: Severity;
  text: string;
  projectId?: string;
  agentId?: string;
  link?: string;
}

export interface Notification {
  id: string;
  at: ISODate;
  title: string;
  body: string;
  severity: Severity;
  read: boolean;
  link?: string;
}

export interface AuditEntry {
  id: string;
  at: ISODate;
  actor: string;
  action: string;
  target: string;
  detail?: string;
}

/* The whole demo ------------------------------------------------------------------------------------- */

export interface SimulationState {
  running: boolean;
  speed: 1 | 2 | 5;
  cursor: number; // next scripted event
  done: string[]; // ids of scripted events applied
  elapsed: number; // simulated seconds since the scenario started
  lastEventAt: number; // elapsed seconds when the last event fired
}

export interface World {
  version: number;
  seq: number; // next number for ids of records created during the demo (deterministic, survives reloads)
  now: ISODate; // the simulated clock
  customers: Customer[];
  people: Person[];
  projects: Project[];
  agentTypes: AgentType[];
  agents: Agent[];
  tasks: Task[];
  executions: Execution[];
  decisions: Decision[];
  risks: Risk[];
  incidents: Incident[];
  artifacts: Artifact[];
  activity: ActivityEvent[]; // newest first
  notifications: Notification[]; // newest first
  audit: AuditEntry[]; // newest first
  sim: SimulationState;
}
