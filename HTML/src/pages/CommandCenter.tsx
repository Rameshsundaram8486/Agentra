/* S01 Executive Command Center: what is happening across the company, what needs people, and how Agentra is doing.
   Every number comes from the shared demo records and moves with the simulation and with people's decisions. */
import { Activity, Bot, ChartColumn, CircleCheck, FolderKanban, Gauge, GitBranch, Hand, Scale, ShieldCheck, TriangleExclamationPoint, Users } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { AgentActivityChart, HealthDonut, LifecycleStrip, RiskMatrix, TaskTrendChart } from "@/components/charts/Charts";
import { ActivityFeed, AttentionList, ProjectHealthTable, Workforce } from "@/components/dashboard/Panels";
import { OwnerBriefing } from "@/components/dashboard/OwnerBriefing";
import { PageHeader } from "@/components/layout/PageHeader";
import { Dot } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { formatDateTime } from "@/lib/format";
import { kpis, openDecisions } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";

export function CommandCenter() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const startSimulation = useDemo((s) => s.startSimulation);
  const navigate = useNavigate();
  const k = kpis(world);
  const running = world.sim.running;
  const waiting = openDecisions(world).length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Executive Command Center"
        crumbs={[{ label: "Company command" }]}
        description="What is happening across Agentra right now: projects, agents, decisions waiting for people, and risks."
        meta={
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-2xs text-fg-muted">
            <Dot tone={running ? "success" : "neutral"} pulse={running} />
            {running ? "Live" : "Paused"} · {formatDateTime(world.now)} (simulated)
          </span>
        }
        actions={!running && <Button size="sm" variant="primary" onClick={startSimulation}>Start the simulation</Button>}
      />

      <section aria-label="Key figures" className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <Kpi label="Active projects" value={k.activeProjects} icon={FolderKanban} onClick={() => navigate("/projects")}
          hint={`${world.projects.filter((p) => p.status === "on_hold").length} on hold, ${world.projects.filter((p) => p.status === "completed").length} completed`} />
        <Kpi label="AI agents working" value={k.activeAgents} icon={Bot} tone="cyan" onClick={() => navigate("/agents")} hint={`of ${world.agents.length} agents`} />
        <Kpi label="Tasks running" value={k.tasksRunning} icon={Activity} onClick={() => navigate("/operations")}
          hint={`${world.tasks.filter((t) => t.state === "waiting_for_review" || t.state === "waiting_for_input").length} waiting for people`} />
        <Kpi label="Pending human decisions" value={k.pendingDecisions} icon={Scale} tone="violet" onClick={() => navigate("/decisions")}
          hint={k.overdueDecisions ? <span className="text-danger">{k.overdueDecisions} overdue</span> : "none overdue"} />
        <Kpi label="Projects at risk" value={k.projectsAtRisk} icon={TriangleExclamationPoint} tone={k.projectsAtRisk ? "warning" : "success"} onClick={() => navigate("/health")} hint="at risk or critical" />
        <Kpi label="Completed deliverables" value={k.completedDeliverables} icon={CircleCheck} tone="success" onClick={() => navigate("/knowledge")} hint={`approved, of ${world.artifacts.length} documents`} />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <OwnerBriefing world={world} />
        <Panel title="Human attention required" subtitle={`${waiting} decision${waiting === 1 ? "" : "s"} waiting; agents never approve`} icon={Hand} flush>
          <AttentionList world={world} role={role} limit={5} />
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <Panel title="Project health" subtitle="Health is derived from open risks, incidents, blocked work and overdue decisions" icon={Gauge} flush
          actions={<Link to="/projects" className="text-xs text-primary-strong hover:underline">All projects</Link>}>
          <ProjectHealthTable world={world} />
        </Panel>
        <Panel title="Live operational activity" subtitle="Newest first" icon={Activity} flush
          actions={<span className="flex items-center gap-1.5 text-2xs text-fg-subtle"><Dot tone={running ? "success" : "neutral"} pulse={running} />{running ? "Live (simulated)" : "Paused"}</span>}>
          <div className="max-h-[430px] overflow-y-auto"><ActivityFeed world={world} limit={14} /></div>
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
        <Panel title="AI workforce" subtitle={`${world.agents.length} agents`} icon={Users} className="2xl:row-span-2"
          actions={<Link to="/agents" className="text-xs text-primary-strong hover:underline">Agent Control Center</Link>}>
          <Workforce world={world} />
        </Panel>
        <Panel title="Project health distribution" icon={Gauge}><HealthDonut world={world} /></Panel>
        <Panel title="Risk distribution" subtitle="Open risks by likelihood and impact" icon={ShieldCheck} actions={<Link to="/risk" className="text-xs text-primary-strong hover:underline">Risks</Link>}>
          <RiskMatrix world={world} />
        </Panel>
        <Panel title="Task completion trend" subtitle="Last 14 days, from task records" icon={ChartColumn}><TaskTrendChart world={world} /></Panel>
        <Panel title="Agent execution activity" subtitle="Runs by agent category, from each agent's record" icon={Bot} className="lg:col-span-2 2xl:col-span-1">
          <AgentActivityChart world={world} />
        </Panel>
      </div>

      <Panel title="Projects across the lifecycle" subtitle="Each project at its current phase; the MVP covers Phases 7 to 11" icon={GitBranch}
        actions={<Link to="/lifecycle" className="text-xs text-primary-strong hover:underline">Delivery Lifecycle</Link>}>
        <LifecycleStrip world={world} />
      </Panel>
    </div>
  );
}
