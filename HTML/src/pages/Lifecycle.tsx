/* S05 Delivery Lifecycle and S06 phase workspaces. The lifecycle shows the 13 phases for the portfolio or one
   project, with the approval gates between them; a phase workspace shows one phase for one project. */
import { useState } from "react";
import { ArrowRight, Bot, FileText, GitBranch, Hand, Lightbulb, ShieldCheck, Workflow } from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { NAV_ITEMS, phasePath } from "@/app/navigation";
import { ReportLinks } from "@/components/dashboard/ReportLinks";
import { PageHeader } from "@/components/layout/PageHeader";
import { gateState, LifecycleRail, portfolioPhase } from "@/components/lifecycle/LifecycleRail";
import { PhaseContent, PreviewView } from "@/components/phases/PhaseViews";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { ARTIFACT_STATUS, DECISION_STATUS, EXECUTION_STATUS, HEALTH, INCIDENT_STATUS, PHASE_STATE, PRIORITY, RISK_STATUS, TASK_STATE } from "@/components/ui/status";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { phaseDef } from "@/data/lifecycle";
import { relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import { agentType, byId, currentPhase, latestVersion, projectHealth, riskScore } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Project, World } from "@/types";

export function Lifecycle() {
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const projectId = params.get("project") ?? "portfolio";
  const project = byId(world.projects, projectId);
  const [selected, setSelected] = useState(project ? currentPhase(project).phase : 9);
  const def = phaseDef(selected);
  const gate = gateState(world, selected, project);
  const here = portfolioPhase(world, selected).projects;
  const agent = agentType(world, def.primaryAgent);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Delivery Lifecycle"
        crumbs={[{ label: "Project operations" }]}
        description="The 13 phases of an Agentra project, each with its agent and the human approval gate that must pass before the next phase starts. The MVP covers Phases 7 to 11."
        actions={
          <select value={projectId} onChange={(e) => setParams((p) => { p.set("project", e.target.value); return p; })} aria-label="Show the lifecycle for" className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
            <option value="portfolio">Whole portfolio</option>
            {world.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        }
      />
      <Panel title={project ? project.name : "Whole portfolio"} subtitle={project ? `Phase ${currentPhase(project).phase} now · ${HEALTH[projectHealth(world, project).health].label}` : "Each phase shows how many projects are in it now"} icon={GitBranch}>
        <LifecycleRail world={world} project={project} selected={selected} onSelect={setSelected} />
        <div className="mt-3 flex flex-wrap gap-2 text-2xs">
          {(["completed", "active", "awaiting_approval", "blocked", "upcoming"] as const).map((s) => <StatusPill key={s} size="sm" meta={PHASE_STATE[s]} />)}
        </div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <Panel title={`Phase ${def.number}: ${def.name}`} subtitle={def.mvp ? "MVP" : "Preview, not in the MVP"} icon={Workflow}
          actions={<Link to={`${phasePath(def.number)}${project ? `?project=${project.id}` : ""}`} className="inline-flex items-center gap-1 text-xs text-primary-strong hover:underline">Open the phase workspace <ArrowRight className="size-3.5" /></Link>}>
          <p className="text-[13px]">{def.description}</p>
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <Field label="Primary agent"><span className="inline-flex items-center gap-1.5"><Avatar name={agent?.name ?? ""} agent size="sm" />{agent?.name}</span></Field>
            <Field label="Entry">{def.number === 1 ? "A new opportunity" : `Phase ${def.number - 1} completed`}</Field>
            <Field label="Exit gate">{def.gate}</Field>
            <Field label="Decided by">{def.gateRoles.map((r) => ROLE_LABELS[r]).join(" or ")}; never an agent</Field>
            <Field label="Gate now"><Tag tone={gate === "passed" ? "success" : gate === "waiting" ? "violet" : gate === "blocked" ? "warning" : "neutral"}>{gate === "passed" ? "passed" : gate === "waiting" ? "waiting for people" : gate}</Tag></Field>
            {project && <Field label="State"><StatusPill size="sm" meta={PHASE_STATE[project.phases[def.number - 1]!.state]} /></Field>}
          </dl>
          {!project && (
            <div className="mt-4">
              <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Projects in this phase now</h3>
              {here.length === 0 ? <p className="text-[13px] text-fg-muted">None.</p> : (
                <ul className="space-y-1">{here.map((p) => <li key={p.id}><Link to={`/projects/${p.id}`} className="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 text-[13px] hover:bg-surface-2">{p.name}<StatusPill size="sm" meta={PHASE_STATE[p.phases[def.number - 1]!.state]} /></Link></li>)}</ul>
              )}
            </div>
          )}
        </Panel>
        {project ? <PhaseContent world={world} project={project} phase={def.number} /> : def.mvp ? (
          here[0] ? <PhaseContent world={world} project={here[0]} phase={def.number} /> : <Panel><EmptyState title="No project is in this phase now" /></Panel>
        ) : (
          <Panel title={`Phase ${def.number} preview`} subtitle="Simulated content; not in the MVP"><PreviewView phase={def.number} /></Panel>
        )}
      </div>
    </div>
  );
}

/* Phase workspaces ------------------------------------------------------------------------------------- */

function projectsForPhase(world: World, phase: number): Project[] {
  const reached = world.projects.filter((p) => p.phases[phase - 1]!.state !== "upcoming");
  const current = reached.filter((p) => currentPhase(p).phase === phase && p.status !== "completed");
  return [...current, ...reached.filter((p) => !current.includes(p))];
}

export function PhaseWorkspace({ phase }: { phase: number }) {
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("overview");
  const def = phaseDef(phase);
  const item = NAV_ITEMS.find((i) => i.phase === phase);
  const candidates = projectsForPhase(world, phase);
  const project = byId(world.projects, params.get("project") ?? undefined) ?? candidates[0];
  const tasks = project ? world.tasks.filter((t) => t.projectId === project.id && t.phase === phase) : [];
  const docs = project ? world.artifacts.filter((a) => a.projectId === project.id && a.phase === phase) : [];
  const decisions = project ? world.decisions.filter((d) => d.projectId === project.id && d.phase === phase) : [];
  const recommendations = decisions.filter((d) => d.kind === "recommendation" || d.kind === "question");
  const approvals = decisions.filter((d) => d.kind === "approval" || d.kind === "escalation");
  const agentIds = new Set(tasks.map((t) => t.agentId).filter(Boolean));
  const runs = project ? world.executions.filter((e) => e.projectId === project.id && (agentIds.has(e.agentId) || tasks.some((t) => t.id === e.taskId))) : [];
  const activity = project ? world.activity.filter((a) => a.projectId === project.id && (!a.agentId || agentIds.has(a.agentId))) : [];
  const risks = project ? world.risks.filter((r) => r.projectId === project.id) : [];
  const incidents = project ? world.incidents.filter((i) => i.projectId === project.id) : [];

  return (
    <div className="space-y-5">
      <PageHeader
        title={item?.label ?? def.name}
        crumbs={[{ label: def.mvp ? "Quality and delivery" : "Business operations" }, { label: `Phase ${phase}`, to: "/lifecycle" }]}
        description={def.description}
        meta={def.mvp ? <Tag tone="primary">MVP</Tag> : <Tag tone="warning">Preview, not in the MVP</Tag>}
        actions={candidates.length > 0 && (
          <select value={project?.id} onChange={(e) => setParams((p) => { p.set("project", e.target.value); return p; })} aria-label="Project" className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
            {candidates.map((p) => <option key={p.id} value={p.id}>{p.name}{currentPhase(p).phase === phase && p.status !== "completed" ? " (in this phase now)" : ""}</option>)}
          </select>
        )}
      />
      {!def.mvp && (
        <p className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-[13px] text-warning">Preview: this phase is outside the MVP (Phases 7 to 11). Its content is simulated to show the intended experience.</p>
      )}
      {!project ? (
        def.mvp ? <Panel><EmptyState title="No project has reached this phase yet" /></Panel> : <Panel title={`Phase ${phase}: ${def.name}`}><PreviewView phase={phase} /></Panel>
      ) : (
        <Tabs value={tab} onValueChange={setTab} items={[
          { value: "overview", label: "Overview" },
          { value: "work", label: "Work items", count: tasks.length },
          { value: "agents", label: "Agent activity", count: runs.length },
          { value: "deliverables", label: "Deliverables", count: docs.length },
          { value: "recommendations", label: "Recommendations", count: recommendations.length },
          { value: "decisions", label: "Human decisions", count: approvals.length },
          { value: "risks", label: "Risks", count: risks.length + incidents.length },
          { value: "reports", label: "Reports" },
        ]}>
          <TabPanel value="overview">
            {def.mvp ? <PhaseContent world={world} project={project} phase={phase} /> : <Panel title={`Phase ${phase}: ${def.name}`} subtitle="Simulated preview"><PreviewView phase={phase} /></Panel>}
          </TabPanel>
          <TabPanel value="work">
            <Panel flush>{tasks.length === 0 ? <EmptyState title="No work items in this phase" /> : (
              <ul className="divide-y divide-line">{tasks.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-[13px]">
                  <Tag>{t.key}</Tag><span className="min-w-0 flex-1">{t.title}<span className="block text-2xs text-fg-subtle">{t.agentId ? byId(world.agents, t.agentId)?.name : "People"}{t.dependsOn.length ? ` · after ${t.dependsOn.map((d) => byId(world.tasks, d)?.key).join(", ")}` : ""}</span></span>
                  <StatusPill size="sm" meta={PRIORITY[t.priority]} /><StatusPill size="sm" meta={TASK_STATE[t.state]} />
                </li>
              ))}</ul>
            )}</Panel>
          </TabPanel>
          <TabPanel value="agents">
            <div className="grid gap-5 lg:grid-cols-2">
              <Panel title="Agent runs" icon={Bot} flush>{runs.length === 0 ? <EmptyState title="No runs recorded" /> : (
                <ul className="divide-y divide-line">{runs.map((e) => (
                  <li key={e.id}><Link to={`/operations?run=${e.id}`} className="flex items-center gap-2 px-4 py-2.5 hover:bg-surface-2"><span className="min-w-0 flex-1 text-[13px]">{e.title}<span className="block text-2xs text-fg-subtle">{byId(world.agents, e.agentId)?.name} · {relative(e.startedAt, world.now)}</span></span><StatusPill size="sm" meta={EXECUTION_STATUS[e.status]} /></Link></li>
                ))}</ul>
              )}</Panel>
              <Panel title="Activity" icon={Workflow} flush>{activity.length === 0 ? <EmptyState title="No activity yet" /> : (
                <ul className="divide-y divide-line">{activity.slice(0, 12).map((a) => <li key={a.id} className="px-4 py-2.5 text-[13px]">{a.text}<span className="block text-2xs text-fg-subtle">{relative(a.at, world.now)}</span></li>)}</ul>
              )}</Panel>
            </div>
          </TabPanel>
          <TabPanel value="deliverables">
            <Panel flush>{docs.length === 0 ? <EmptyState title="No deliverables yet" /> : (
              <ul className="divide-y divide-line">{docs.map((d) => { const v = latestVersion(d); return (
                <li key={d.id}><Link to={`/knowledge?doc=${d.id}`} className="flex items-center gap-2 px-4 py-2.5 hover:bg-surface-2"><FileText className="size-4 text-fg-subtle" /><span className="min-w-0 flex-1 text-[13px]">{d.title} v{v.no}<span className="block text-2xs text-fg-subtle">{d.excerpt}</span></span><StatusPill size="sm" meta={ARTIFACT_STATUS[v.status]} /></Link></li>
              ); })}</ul>
            )}</Panel>
          </TabPanel>
          <TabPanel value="recommendations"><DecisionList world={world} decisions={recommendations} empty="No recommendations in this phase" icon={Lightbulb} /></TabPanel>
          <TabPanel value="decisions"><DecisionList world={world} decisions={approvals} empty="No approvals or escalations in this phase" icon={Hand} /></TabPanel>
          <TabPanel value="risks">
            <Panel flush>{risks.length + incidents.length === 0 ? <EmptyState title="No risks or incidents" /> : (
              <ul className="divide-y divide-line">
                {risks.map((r) => <li key={r.id} className="flex items-center gap-2 px-4 py-2.5 text-[13px]"><Tag tone={riskScore(r) >= 16 ? "danger" : riskScore(r) >= 12 ? "warning" : "primary"}>{r.code} · {riskScore(r)}</Tag><span className="flex-1">{r.title}</span><StatusPill size="sm" meta={RISK_STATUS[r.status]} /></li>)}
                {incidents.map((i) => <li key={i.id}><Link to={`/owner?incident=${i.id}`} className="flex items-center gap-2 px-4 py-2.5 text-[13px] hover:bg-surface-2"><ShieldCheck className="size-4 text-fg-subtle" /><span className="flex-1">{i.code} {i.title}</span><StatusPill size="sm" meta={INCIDENT_STATUS[i.status]} /></Link></li>)}
              </ul>
            )}</Panel>
          </TabPanel>
          <TabPanel value="reports">
            <ReportLinks projectId={project?.id} ids={phase === 10 ? ["qa", "defects", "workflow", "approvals"] : ["projects", "workflow", "approvals", "risks"]} title={`Reports for Phase ${phase}${project ? `, ${project.name}` : ""}`} />
          </TabPanel>
        </Tabs>
      )}
    </div>
  );
}

function DecisionList({ world, decisions, empty, icon: Icon }: { world: World; decisions: World["decisions"]; empty: string; icon: typeof Hand }) {
  return (
    <Panel flush>{decisions.length === 0 ? <EmptyState icon={Icon} title={empty} /> : (
      <ul className="divide-y divide-line">{decisions.map((d) => (
        <li key={d.id}><Link to={`/decisions?id=${d.id}`} className="flex items-center gap-2 px-4 py-2.5 hover:bg-surface-2">
          <Tag>{d.code}</Tag>
          <span className="min-w-0 flex-1 text-[13px]">{d.title}<span className="block text-2xs text-fg-subtle">{byId(world.agents, d.originAgentId)?.name} · needs {d.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")}</span></span>
          <StatusPill size="sm" meta={DECISION_STATUS[d.status]} />
        </Link></li>
      ))}</ul>
    )}</Panel>
  );
}

/** One route per phase workspace. */
export const RequirementsWorkspace = () => <PhaseWorkspace phase={7} />;
export const ArchitectureWorkspace = () => <PhaseWorkspace phase={8} />;
export const DevelopmentWorkspace = () => <PhaseWorkspace phase={9} />;
export const QaWorkspace = () => <PhaseWorkspace phase={10} />;
export const UatWorkspace = () => <PhaseWorkspace phase={11} />;
export const ReleasesWorkspace = () => <PhaseWorkspace phase={12} />;
export const SalesWorkspace = () => <PhaseWorkspace phase={1} />;
export const DiscoveryWorkspace = () => <PhaseWorkspace phase={2} />;
export const ProposalsWorkspace = () => <PhaseWorkspace phase={3} />;
export const CommercialWorkspace = () => <PhaseWorkspace phase={5} />;
