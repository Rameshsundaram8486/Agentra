import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { HashRouter, Route, Routes } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/States";
import { CommandCenter } from "@/pages/CommandCenter";
import { Placeholder } from "@/pages/Placeholder";
import { NAV_ITEMS } from "./navigation";
import { Providers } from "./providers";

const named = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) => lazy(() => load().then((m) => ({ default: m[name] })));

// Pages other than the Command Center load when first opened, so the first screen loads quickly.
const LiveOperations = named(() => import("@/pages/LiveOperations"), "LiveOperations");
const AgentControlCenter = named(() => import("@/pages/Agents"), "AgentControlCenter");
const AgentDirectory = named(() => import("@/pages/Agents"), "AgentDirectory");
const ExecutionHistory = named(() => import("@/pages/Agents"), "ExecutionHistory");
const Gallery = named(() => import("@/pages/Gallery"), "Gallery");
const Projects = named(() => import("@/pages/Projects"), "Projects");
const Pipeline = named(() => import("@/pages/Projects"), "Pipeline");
const DeliveryBoard = named(() => import("@/pages/Projects"), "DeliveryBoard");
const Milestones = named(() => import("@/pages/Projects"), "Milestones");
const ProjectWorkspace = named(() => import("@/pages/ProjectWorkspace"), "ProjectWorkspace");
const DecisionCenter = named(() => import("@/pages/Decisions"), "DecisionCenter");
const ApprovalInbox = named(() => import("@/pages/Decisions"), "ApprovalInbox");
const Recommendations = named(() => import("@/pages/Decisions"), "Recommendations");
const Escalations = named(() => import("@/pages/Decisions"), "Escalations");
const ProjectOwnerAgent = named(() => import("@/pages/Oversight"), "ProjectOwnerAgent");
const ProjectHealth = named(() => import("@/pages/Oversight"), "ProjectHealth");
const RiskCompliance = named(() => import("@/pages/Oversight"), "RiskCompliance");
const CompanyPerformance = named(() => import("@/pages/Analytics"), "CompanyPerformance");
const AgentPerformance = named(() => import("@/pages/Analytics"), "AgentPerformance");
const Reports = named(() => import("@/pages/Analytics"), "Reports");
const KnowledgeBase = named(() => import("@/pages/Knowledge"), "KnowledgeBase");
const Integrations = named(() => import("@/pages/Platform"), "Integrations");
const ModelGateway = named(() => import("@/pages/Platform"), "ModelGateway");
const AgentConfiguration = named(() => import("@/pages/Governance"), "AgentConfiguration");
const WorkflowConfiguration = named(() => import("@/pages/Governance"), "WorkflowConfiguration");
const UsersPermissions = named(() => import("@/pages/Governance"), "UsersPermissions");
const SystemSettings = named(() => import("@/pages/Governance"), "SystemSettings");
const lifecycle = (name: "Lifecycle" | "RequirementsWorkspace" | "ArchitectureWorkspace" | "DevelopmentWorkspace" | "QaWorkspace" | "UatWorkspace" | "ReleasesWorkspace" | "SalesWorkspace" | "DiscoveryWorkspace" | "ProposalsWorkspace" | "CommercialWorkspace") =>
  named(() => import("@/pages/Lifecycle"), name);

/** Built pages by navigation id; the rest show their placeholder until their stage. */
const PAGES: Record<string, ComponentType | LazyExoticComponent<ComponentType>> = {
  command: CommandCenter,
  operations: LiveOperations,
  agents: AgentControlCenter,
  directory: AgentDirectory,
  history: ExecutionHistory,
  projects: Projects,
  pipeline: Pipeline,
  board: DeliveryBoard,
  milestones: Milestones,
  lifecycle: lifecycle("Lifecycle"),
  requirements: lifecycle("RequirementsWorkspace"),
  architecture: lifecycle("ArchitectureWorkspace"),
  development: lifecycle("DevelopmentWorkspace"),
  qa: lifecycle("QaWorkspace"),
  uat: lifecycle("UatWorkspace"),
  releases: lifecycle("ReleasesWorkspace"),
  sales: lifecycle("SalesWorkspace"),
  discovery: lifecycle("DiscoveryWorkspace"),
  proposals: lifecycle("ProposalsWorkspace"),
  commercial: lifecycle("CommercialWorkspace"),
  decisions: DecisionCenter,
  approvals: ApprovalInbox,
  recommendations: Recommendations,
  escalations: Escalations,
  owner: ProjectOwnerAgent,
  health: ProjectHealth,
  risk: RiskCompliance,
  performance: CompanyPerformance,
  "agent-performance": AgentPerformance,
  reports: Reports,
  knowledge: KnowledgeBase,
  integrations: Integrations,
  gateway: ModelGateway,
  "agent-config": AgentConfiguration,
  "workflow-config": WorkflowConfiguration,
  users: UsersPermissions,
  settings: SystemSettings,
};

function Loading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-72" />
      <Skeleton className="h-4 w-[28rem] max-w-full" />
      <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
      <Skeleton className="h-80" />
    </div>
  );
}

// Hash routes, so the built demo works from any static host without server rewrites. Every navigation item has a
// route; pages not built yet show what they will contain (pages/Placeholder.tsx).
export function App() {
  return (
    <Providers>
      <HashRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<AppShell />}>
              {NAV_ITEMS.map((item) => {
                const Page = PAGES[item.id];
                return <Route key={item.id} path={item.path} element={Page ? <Suspense fallback={<Loading />}><Page /></Suspense> : <Placeholder item={item} />} />;
              })}
              <Route path="/projects/:projectId" element={<Suspense fallback={<Loading />}><ProjectWorkspace /></Suspense>} />
              <Route path="/design-system" element={<Suspense fallback={<Loading />}><Gallery /></Suspense>} />
              <Route path="*" element={<Placeholder />} />
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </Providers>
  );
}
