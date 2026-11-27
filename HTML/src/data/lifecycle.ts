/* The 13-phase Agentra delivery lifecycle (Product Docs, Phase-01 ... Phase-13). The MVP is Phases 7-11. */
import type { PhaseDefinition } from "@/types";

export const PHASES: PhaseDefinition[] = [
  {
    number: 1, key: "sales", name: "Sales and Lead Generation", short: "Sales", mvp: false, primaryAgent: "sales_lead_generation",
    gate: "Qualified lead accepted", gateRoles: ["owner"],
    description: "Finds and qualifies leads in the target market and prepares them for a first conversation.",
  },
  {
    number: 2, key: "discovery", name: "Meeting Scheduling and Customer Discovery", short: "Discovery", mvp: false, primaryAgent: "opportunity_discovery",
    gate: "Discovery notes confirmed", gateRoles: ["owner", "project_manager"],
    description: "Schedules meetings, captures discovery notes with consent and confirms the customer's needs.",
  },
  {
    number: 3, key: "proposal", name: "Technical and Commercial Proposal", short: "Proposal", mvp: false, primaryAgent: "proposal_estimation",
    gate: "Proposal approved for submission", gateRoles: ["owner"],
    description: "Prepares the technical approach, estimate and commercial proposal for human approval.",
  },
  {
    number: 4, key: "negotiation", name: "Customer Presentation and Negotiation", short: "Negotiation", mvp: false, primaryAgent: "presentation",
    gate: "Negotiated terms approved", gateRoles: ["owner"],
    description: "Presents the proposal and records negotiated changes; people agree the commercial terms.",
  },
  {
    number: 5, key: "award", name: "Project Award and PO Validation", short: "Award", mvp: false, primaryAgent: "commercial_control",
    gate: "Purchase order validated", gateRoles: ["owner"],
    description: "Validates the award and purchase order against the approved proposal before work starts.",
  },
  {
    number: 6, key: "kickoff", name: "Project Kickoff and Governance", short: "Kickoff", mvp: false, primaryAgent: "project_manager",
    gate: "Project charter approved", gateRoles: ["owner", "project_manager"],
    description: "Sets up the project, team, governance cadence and charter.",
  },
  {
    number: 7, key: "requirements", name: "Business Analysis and Requirements", short: "Requirements", mvp: true, primaryAgent: "business_analyst",
    gate: "Requirements baseline approved", gateRoles: ["reviewer", "owner"],
    description: "Clarifies the brief, drafts requirements with acceptance criteria and traceability, and baselines them.",
  },
  {
    number: 8, key: "design", name: "Solution Architecture and Technical Design", short: "Architecture", mvp: true, primaryAgent: "solution_architect",
    gate: "Design baseline and backlog approved", gateRoles: ["reviewer", "owner"],
    description: "Compares options, designs the solution, passes security and feasibility reviews and plans the backlog.",
  },
  {
    number: 9, key: "development", name: "Development and Implementation", short: "Development", mvp: true, primaryAgent: "developer",
    gate: "Implementation report approved", gateRoles: ["reviewer", "owner"],
    description: "Implements work items as change sets, built and tested in sandbox VMs, reviewed and merged.",
  },
  {
    number: 10, key: "qa", name: "Quality Assurance and Testing", short: "QA", mvp: true, primaryAgent: "qa_tester",
    gate: "QA completion report approved", gateRoles: ["reviewer", "owner"],
    description: "Plans and runs tests, manages defects and retests, and reports quality for release to UAT.",
  },
  {
    number: 11, key: "uat", name: "Customer UAT and Sign-Off", short: "UAT", mvp: true, primaryAgent: "uat_release",
    gate: "UAT sign-off recorded by the customer", gateRoles: ["customer_approver"],
    description: "Supports customer acceptance testing, triages feedback and records the customer's sign-off.",
  },
  {
    number: 12, key: "golive", name: "Production Go-Live", short: "Go-live", mvp: false, primaryAgent: "release_deployment",
    gate: "Go-live approved", gateRoles: ["owner"],
    description: "Plans and executes the production release with rollback readiness and human approval.",
  },
  {
    number: 13, key: "closure", name: "Project Closure", short: "Closure", mvp: false, primaryAgent: "project_manager",
    gate: "Closure report approved", gateRoles: ["owner"],
    description: "Hands over, captures lessons learned and closes the project.",
  },
];

export function phaseDef(number: number): PhaseDefinition {
  const phase = PHASES.find((p) => p.number === number);
  if (!phase) throw new Error(`Unknown phase ${number}`);
  return phase;
}
