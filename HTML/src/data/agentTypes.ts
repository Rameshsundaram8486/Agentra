/* The agent roster: the 20 agent definitions in config/agents/, plus a Reporting agent shown for the demo. Models
   follow ADR 0001: every agent calls claude-opus-5-5 through the model gateway, with effort set per agent. */
import type { AgentType } from "@/types";

const MODEL = "claude-opus-5-5";

export const AGENT_TYPES: AgentType[] = [
  // Sales and business operations (previews: Phases 1-5)
  { key: "sales_lead_generation", name: "Lead Generation Agent", category: "sales", phases: [1], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: false,
    description: "Finds and qualifies leads in the target market against the ideal customer profile.", tools: ["CRM read", "Web research", "Draft outreach (human sends)"] },
  { key: "market_research", name: "Market Research Agent", category: "sales", phases: [1], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: false,
    description: "Researches sectors, competitors and buying signals for sales planning.", tools: ["Web research", "Knowledge base read"] },
  { key: "opportunity_discovery", name: "Opportunity & Discovery Agent", category: "sales", phases: [2], model: MODEL, effort: "high", autonomy: "supervised", inMvp: false,
    description: "Prepares discovery meetings and turns notes into a structured opportunity.", tools: ["Calendar read", "Meeting notes", "CRM write (draft)"] },
  { key: "scheduling", name: "Scheduling Agent", category: "sales", phases: [2], model: MODEL, effort: "low", autonomy: "controlled", inMvp: false,
    description: "Proposes meeting times and prepares invitations for people to send.", tools: ["Calendar read", "Draft invitations"] },
  { key: "voice_meeting", name: "Meeting Assistant Agent", category: "sales", phases: [2, 4], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: false,
    description: "Captures meeting minutes and actions, only with recorded consent.", tools: ["Transcripts (with consent)", "Minutes draft"] },
  { key: "proposal_estimation", name: "Proposal & Estimation Agent", category: "sales", phases: [3], model: MODEL, effort: "high", autonomy: "supervised", inMvp: false,
    description: "Drafts the technical approach, estimate and proposal for human approval.", tools: ["Estimation models", "Proposal templates", "Knowledge base read"] },
  { key: "presentation", name: "Presentation Agent", category: "sales", phases: [4], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: false,
    description: "Builds customer presentations from the approved proposal.", tools: ["Slide templates", "Proposal read"] },
  { key: "commercial_control", name: "Commercial Control Agent", category: "sales", phases: [5], model: MODEL, effort: "high", autonomy: "supervised", inMvp: false,
    description: "Checks awards and purchase orders against the approved commercial terms.", tools: ["Contract read", "PO validation checks"] },

  // Delivery (MVP: Phases 7-11)
  { key: "business_analyst", name: "Business Analyst Agent", category: "business_analysis", phases: [7], model: MODEL, effort: "high", autonomy: "supervised", inMvp: true,
    description: "Clarifies the brief, drafts requirements with acceptance criteria and keeps traceability.", tools: ["Document read", "Decision requests", "Requirements write (draft)"] },
  { key: "solution_architect", name: "Solution Architect Agent", category: "architecture", phases: [8], model: MODEL, effort: "high", autonomy: "supervised", inMvp: true,
    description: "Compares solution options and drafts the design that covers every confirmed requirement.", tools: ["Requirements read", "Design write (draft)", "Decision requests"] },
  { key: "security_reviewer", name: "Security Reviewer Agent", category: "architecture", phases: [8], model: MODEL, effort: "high", autonomy: "supervised", inMvp: true,
    description: "Reviews each design version against the security checklist; a person signs the review off.", tools: ["Design read", "Security checklist"] },
  { key: "developer", name: "Developer Agent", category: "development", phases: [8, 9], model: MODEL, effort: "high", autonomy: "controlled", inMvp: true,
    description: "Reviews feasibility, plans the backlog and implements work items as change sets in sandbox VMs.", tools: ["Repository read", "Change set write", "Sandbox VM (build and test)"] },
  { key: "qa_tester", name: "QA Agent", category: "qa", phases: [10], model: MODEL, effort: "high", autonomy: "controlled", inMvp: true,
    description: "Plans and runs tests in sandbox VMs, logs defects and retests fixes.", tools: ["Test plans", "Sandbox VM (test runs)", "Defect log"] },
  { key: "uat_release", name: "UAT & Release Agent", category: "qa", phases: [11, 12], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: true,
    description: "Prepares UAT scenarios, triages customer feedback and prepares sign-off; never records sign-off itself.", tools: ["UAT scenarios", "Feedback triage", "Sign-off pack"] },
  { key: "release_deployment", name: "Release & Deployment Agent", category: "development", phases: [12], model: MODEL, effort: "high", autonomy: "supervised", inMvp: false,
    description: "Prepares release plans and rollback steps; production changes need human approval.", tools: ["Release checklist", "Deployment plan"] },

  // Project management and governance
  { key: "project_manager", name: "Project Manager Agent", category: "project_management", phases: [6, 13], model: MODEL, effort: "medium", autonomy: "controlled", inMvp: true,
    description: "Tracks progress, milestones and dependencies and prepares status updates.", tools: ["Workflow read", "Status reports (draft)"] },
  { key: "customer_success", name: "Customer Success Agent", category: "project_management", phases: [11, 13], model: MODEL, effort: "medium", autonomy: "supervised", inMvp: false,
    description: "Keeps the customer relationship on track and flags satisfaction risks.", tools: ["CRM read", "Feedback summaries"] },
  { key: "project_owner", name: "Project Owner Agent", category: "governance", phases: [6, 7, 8, 9, 10, 11, 12, 13], model: MODEL, effort: "xhigh", autonomy: "supervised", inMvp: true,
    description: "Oversees every project: detects risks, stuck work, failed runs and overdue decisions, and proposes corrective actions.", tools: ["Read all project records", "Incident and RCA drafts", "Escalations"] },
  { key: "company_orchestrator", name: "Company Orchestrator Agent", category: "governance", phases: [], model: MODEL, effort: "high", autonomy: "supervised", inMvp: false,
    description: "Balances work across agents and projects and routes tasks to the right agent.", tools: ["Workflow read", "Task routing (proposals)"] },
  { key: "knowledge_operations", name: "Knowledge Operations Agent", category: "governance", phases: [13], model: MODEL, effort: "medium", autonomy: "controlled", inMvp: false,
    description: "Curates the knowledge base from approved project documents and lessons learned.", tools: ["Knowledge base write (draft)", "Document read"] },
  { key: "reporting", name: "Reporting Agent", category: "reporting", phases: [7, 8, 9, 10, 11], model: MODEL, effort: "medium", autonomy: "controlled", inMvp: true,
    description: "Prepares executive and detailed reports from recorded workflow data, never from narrative alone.", tools: ["Read records", "Report templates"] },
];

export const CATEGORY_LABELS: Record<AgentType["category"], string> = {
  sales: "Sales agents",
  business_analysis: "Business analysis agents",
  architecture: "Architecture agents",
  development: "Development agents",
  qa: "QA agents",
  project_management: "Project management agents",
  governance: "Governance agents",
  reporting: "Reporting agents",
};
