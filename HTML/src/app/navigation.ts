/* The navigation, defined once: the sidebar, the command palette, the routes and the page headers all read it.
   Each page names the build stage that delivers it; until then it shows what it will contain. */
import {
  Activity, Bot, BookOpen, Briefcase, ChartColumn, ClipboardCheck, Code, Cpu, FileText, FolderKanban, Gauge, GitBranch, Handshake,
  History, Inbox, Kanban, Layers, LayoutDashboard, Lightbulb, Milestone, Network, Plug, Radar, Rocket, Scale, Settings, ShieldCheck,
  ShieldExclamationPoint, Signature, Target, TestTubeDiagonal, TrendingUp, Users, Workflow, type LucideIcon,
} from "lucide-react";
import type { Role, World } from "@/types";
import { isOpenDecision, projectHealth } from "@/store/selectors";
import type { Tone } from "@/components/ui/status";

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: LucideIcon;
  stage: number; // the build stage that delivers the page
  screen?: string; // the brief's screen number, e.g. S01
  description: string;
  preview?: boolean; // outside the MVP (Phases 7-11)
  phase?: number; // phase workspace pages
  count?: (world: World, role: Role) => { value: number; tone: Tone; label: string } | null;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

const pendingFor = (world: World, role: Role, kind?: string) =>
  world.decisions.filter((d) => isOpenDecision(d) && d.allowedRoles.includes(role) && (kind === undefined || d.kind === kind)).length;

export const NAVIGATION: NavGroup[] = [
  {
    id: "company", label: "Company command",
    items: [
      { id: "command", label: "Executive Command Center", path: "/", icon: LayoutDashboard, stage: 3, screen: "S01",
        description: "What is happening across the company: projects, agents, decisions waiting for people, risks and the Project Owner Agent's briefing." },
      { id: "performance", label: "Company Performance", path: "/performance", icon: TrendingUp, stage: 6, screen: "S10",
        description: "Delivery, quality, agent and approval performance across the company, with drill-down to each project." },
      { id: "operations", label: "Live Operations", path: "/operations", icon: Activity, stage: 4, screen: "S02",
        description: "Workflow runs in flight, agent handoffs, queues, failures and retries, with simulated pause, resume and retry.",
        count: (w) => ({ value: w.executions.filter((e) => e.status === "running" || e.status === "retrying").length, tone: "primary", label: "runs in flight" }) },
    ],
  },
  {
    id: "projects", label: "Project operations",
    items: [
      { id: "projects", label: "Projects", path: "/projects", icon: FolderKanban, stage: 4, screen: "S03",
        description: "The project portfolio as a table, cards or a kanban board, with health, phase, budget and dates.",
        count: (w) => {
          const atRisk = w.projects.filter((p) => ["at_risk", "critical"].includes(projectHealth(w, p).health)).length;
          return { value: atRisk, tone: "warning", label: "projects at risk" };
        } },
      { id: "lifecycle", label: "Delivery Lifecycle", path: "/lifecycle", icon: GitBranch, stage: 4, screen: "S05",
        description: "The 13-phase delivery lifecycle with its approval gates; the MVP covers Phases 7 to 11." },
      { id: "pipeline", label: "Project Pipeline", path: "/pipeline", icon: Layers, stage: 4, screen: "S03",
        description: "Projects grouped by lifecycle phase, from sales to closure." },
      { id: "board", label: "Project Delivery Board", path: "/board", icon: Kanban, stage: 4, screen: "S03",
        description: "Work items across projects on a board, by workflow state." },
      { id: "milestones", label: "Milestones and Dependencies", path: "/milestones", icon: Milestone, stage: 4, screen: "S04",
        description: "Milestones on a timeline across projects, with the dependencies between work items." },
    ],
  },
  {
    id: "workforce", label: "AI workforce",
    items: [
      { id: "agents", label: "Agent Control Center", path: "/agents", icon: Bot, stage: 4, screen: "S08",
        description: "The AI workforce by category: status, current work, model, permissions and an activity console.",
        count: (w) => ({ value: w.agents.filter((a) => a.status === "failed" || a.status === "blocked").length, tone: "warning", label: "agents blocked or failed" }) },
      { id: "directory", label: "Agent Directory", path: "/agents/directory", icon: Users, stage: 4, screen: "S08",
        description: "Every agent, its role, the phases it works in, its tools and its autonomy level." },
      { id: "history", label: "Agent Execution History", path: "/agents/history", icon: History, stage: 4, screen: "S02",
        description: "Every agent run with its inputs, outputs, logs, cost and outcome." },
      { id: "agent-performance", label: "Agent Performance", path: "/agents/performance", icon: Gauge, stage: 6, screen: "S10",
        description: "Success rates, run times and costs per agent." },
      { id: "owner", label: "Project Owner Agent", path: "/owner", icon: Radar, stage: 6, screen: "S09",
        description: "The Project Owner Agent's oversight: health assessment, risks, stuck work, failed runs and root-cause analyses." },
    ],
  },
  {
    id: "governance", label: "Human governance",
    items: [
      { id: "decisions", label: "Decision Center", path: "/decisions", icon: Scale, stage: 5, screen: "S07",
        description: "Every agent recommendation and approval waiting for a person, with the evidence, the options and the full history.",
        count: (w, r) => ({ value: pendingFor(w, r), tone: "violet", label: "decisions you can make" }) },
      { id: "approvals", label: "Approval Inbox", path: "/approvals", icon: Inbox, stage: 5, screen: "S07",
        description: "Approvals waiting for your role: baselines, change sets, reviews and sign-offs.",
        count: (w, r) => ({ value: pendingFor(w, r, "approval"), tone: "violet", label: "approvals for your role" }) },
      { id: "recommendations", label: "Recommendations", path: "/recommendations", icon: Lightbulb, stage: 5, screen: "S07",
        description: "Agent recommendations and questions, with what the agent recommended and what people decided." },
      { id: "escalations", label: "Escalations", path: "/escalations", icon: ShieldExclamationPoint, stage: 5, screen: "S07",
        description: "Escalations raised by agents and the Project Owner Agent.",
        count: (w) => ({ value: w.decisions.filter((d) => isOpenDecision(d) && d.kind === "escalation").length, tone: "danger", label: "open escalations" }) },
    ],
  },
  {
    id: "business", label: "Business operations",
    items: [
      { id: "sales", label: "Sales and Leads", path: "/business/sales", icon: Target, stage: 4, phase: 1, preview: true, description: "Phase 1: leads, qualification and outreach drafts." },
      { id: "discovery", label: "Customer Discovery", path: "/business/discovery", icon: Handshake, stage: 4, phase: 2, preview: true, description: "Phase 2: meetings and discovery notes." },
      { id: "proposals", label: "Proposals and Estimates", path: "/business/proposals", icon: FileText, stage: 4, phase: 3, preview: true, description: "Phase 3: technical and commercial proposals." },
      { id: "commercial", label: "Commercial Operations", path: "/business/commercial", icon: Briefcase, stage: 4, phase: 5, preview: true, description: "Phases 4 and 5: negotiation, award and purchase order validation." },
    ],
  },
  {
    id: "delivery", label: "Quality and delivery",
    items: [
      { id: "requirements", label: "Requirements", path: "/delivery/requirements", icon: ClipboardCheck, stage: 4, phase: 7, screen: "S06", description: "Phase 7: requirements, traceability and the baseline." },
      { id: "architecture", label: "Solution Architecture", path: "/delivery/architecture", icon: Network, stage: 4, phase: 8, screen: "S06", description: "Phase 8: options, design, security and feasibility reviews, the backlog." },
      { id: "development", label: "Development", path: "/delivery/development", icon: Code, stage: 4, phase: 9, screen: "S06", description: "Phase 9: work items, change sets, sandbox builds and tests, merges." },
      { id: "qa", label: "QA and Testing", path: "/delivery/qa", icon: TestTubeDiagonal, stage: 4, phase: 10, screen: "S06", description: "Phase 10: test plan, runs, defects and retests." },
      { id: "uat", label: "Customer UAT", path: "/delivery/uat", icon: Signature, stage: 4, phase: 11, screen: "S06", description: "Phase 11: UAT scenarios, feedback and the customer's sign-off." },
      { id: "releases", label: "Production Releases", path: "/delivery/releases", icon: Rocket, stage: 4, phase: 12, preview: true, description: "Phase 12: release plans, approvals and go-live." },
    ],
  },
  {
    id: "intelligence", label: "Intelligence",
    items: [
      { id: "reports", label: "Reports and Analytics", path: "/reports", icon: ChartColumn, stage: 6, screen: "S10", description: "Executive and detailed reports built from records, with preview and export." },
      { id: "health", label: "Project Health", path: "/health", icon: Activity, stage: 6, screen: "S09", description: "Each project's health and the records behind it." },
      { id: "risk", label: "Risk and Compliance", path: "/risk", icon: ShieldCheck, stage: 6, screen: "S09",
        description: "Risks, incidents and their root-cause analyses.",
        count: (w) => ({ value: w.risks.filter((r) => r.status !== "closed" && r.likelihood * r.impact >= 12).length, tone: "danger", label: "high risks open" }) },
      { id: "knowledge", label: "Knowledge Base", path: "/knowledge", icon: BookOpen, stage: 6, screen: "S11", description: "Documents, versions, approvals and traceability." },
    ],
  },
  {
    id: "admin", label: "Administration",
    items: [
      { id: "integrations", label: "Integrations", path: "/admin/integrations", icon: Plug, stage: 6, screen: "S12", description: "Microsoft 365, SharePoint, Azure, GitHub, Teams and Outlook connections (simulated)." },
      { id: "gateway", label: "Model Gateway", path: "/admin/model-gateway", icon: Cpu, stage: 6, screen: "S12", description: "The Claude API through the model gateway: routing, usage, latency and the monthly cap." },
      { id: "agent-config", label: "Agent Configuration", path: "/admin/agents", icon: Bot, stage: 6, screen: "S13", description: "Agent definitions, prompts, tools and autonomy levels." },
      { id: "workflow-config", label: "Workflow Configuration", path: "/admin/workflows", icon: Workflow, stage: 6, screen: "S13", description: "Phase lifecycles, gates and approval policies." },
      { id: "users", label: "Users and Permissions", path: "/admin/users", icon: Users, stage: 6, screen: "S13", description: "People, roles and what each role may do." },
      { id: "settings", label: "System Settings", path: "/admin/settings", icon: Settings, stage: 6, screen: "S13", description: "Security, notifications and the audit log." },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAVIGATION.flatMap((g) => g.items);

export function navItemFor(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => item.path === pathname) ?? NAV_ITEMS.filter((i) => i.path !== "/" && pathname.startsWith(i.path)).sort((a, b) => b.path.length - a.path.length)[0];
}
