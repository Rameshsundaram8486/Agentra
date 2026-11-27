/* S04 Project Workspace: one project's header and 13 tabs (overview, lifecycle, agents, tasks, the five MVP phase
   views, decisions, risks and issues, documents, reports). The open tab is kept in the address (?tab=). */
import { useState } from "react";
import { CalendarClock, FileText, Flag, Hand, History, ShieldCheck, Users } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { LifecycleRail } from "@/components/lifecycle/LifecycleRail";
import { PhaseContent } from "@/components/phases/PhaseViews";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState, Progress } from "@/components/ui/States";
import { AGENT_STATUS, ARTIFACT_STATUS, DECISION_STATUS, HEALTH, INCIDENT_STATUS, PRIORITY, RISK_STATUS, TASK_STATE } from "@/components/ui/status";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { phaseDef } from "@/data/lifecycle";
import { aed, formatDate, relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import { actorName, byId, completion, currentPhase, isOpenDecision, latestVersion, projectAgents, projectHealth, riskScore } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Task } from "@/types";

const TABS = [
  ["overview", "Overview"], ["lifecycle", "Lifecycle"], ["agents", "Agents"], ["tasks", "Tasks"], ["requirements", "Requirements"], ["architecture", "Architecture"],
  ["development", "Development"], ["qa", "QA and Testing"], ["uat", "UAT"], ["decisions", "Decisions"], ["risks", "Risks and Issues"], ["documents", "Documents"], ["reports", "Reports"],
] as const;
const PHASE_TABS: Record<string, number> = { requirements: 7, architecture: 8, development: 9, qa: 10, uat: 11 };

export function ProjectWorkspace() {
  const { projectId } = useParams();
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const project = byId(world.projects, projectId);
  const [phase, setPhase] = useState(project ? currentPhase(project).phase : 7);
  if (!project) {
    return <Panel><EmptyState title="Project not found" action={<Link to="/projects" className="text-[13px] text-primary-strong hover:underline">All projects</Link>} /></Panel>;
  }
  const tab = params.get("tab") ?? "overview";
  const setTab = (value: string) => setParams((p) => { p.set("tab", value); return p; }, { replace: true });
  const health = projectHealth(world, project);
  const current = currentPhase(project);
  const tasks = world.tasks.filter((t) => t.projectId === project.id);
  const decisions = world.decisions.filter((d) => d.projectId === project.id);
  const open = decisions.filter(isOpenDecision);
  const risks = world.risks.filter((r) => r.projectId === project.id);
  const incidents = world.incidents.filter((i) => i.projectId === project.id);
  const docs = world.artifacts.filter((a) => a.projectId === project.id);
  const agents = projectAgents(world, project.id);
  const activity = world.activity.filter((a) => a.projectId === project.id);
  const customer = byId(world.customers, project.customerId);

  return (
    <div className="space-y-5">
      <PageHeader
        title={project.name}
        crumbs={[{ label: "Projects", to: "/projects" }, { label: project.code }]}
        description={project.summary}
        meta={<><StatusPill meta={HEALTH[health.health]} /><Tag>{project.status.replace("_", " ")}</Tag></>}
      />
      <section aria-label="Project summary" className="grid grid-cols-2 gap-3 rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel md:grid-cols-3 xl:grid-cols-6">
        <Field label="Customer">{customer?.name}<span className="block text-2xs text-fg-subtle">{customer?.sector} · {customer?.city}</span></Field>
        <Field label="Project owner"><span className="inline-flex items-center gap-1.5"><Avatar name={actorName(world, project.managerId)} size="sm" />{actorName(world, project.managerId)}</span></Field>
        <Field label="Current phase">{current.phase}. {phaseDef(current.phase).name}{!phaseDef(current.phase).mvp && <Tag className="ml-1">Preview</Tag>}</Field>
        <Field label="Completion"><div className="flex items-center gap-2"><Progress value={completion(project)} label="Completion" /><span className="tabular">{completion(project)}%</span></div></Field>
        <Field label="Target completion">{formatDate(project.targetDate, true)}<span className="block text-2xs text-fg-subtle">started {formatDate(project.startDate, true)}</span></Field>
        <Field label="Budget used">{Math.round((project.spentAed / project.budgetAed) * 100)}%<span className="block text-2xs text-fg-subtle">{aed(project.spentAed)} of {aed(project.budgetAed)} (sample)</span></Field>
      </section>
      {health.health !== "on_track" && health.health !== "completed" && (
        <p className={cn("rounded-lg border px-3 py-2 text-[13px]", health.health === "critical" ? "border-danger/30 bg-danger-soft text-danger" : "border-warning/30 bg-warning-soft text-warning")}>
          {HEALTH[health.health].label}: {health.reasons.slice(0, 3).join("; ")}
        </p>
      )}

      <Tabs value={tab} onValueChange={setTab} items={TABS.map(([value, label]) => ({
        value, label,
        count: value === "tasks" ? tasks.length : value === "decisions" ? open.length : value === "risks" ? risks.filter((r) => r.status !== "closed").length + incidents.filter((i) => i.status !== "closed").length : value === "documents" ? docs.length : value === "agents" ? agents.length : undefined,
      }))}>
        <TabPanel value="overview">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <div className="space-y-5">
              <Panel title="Milestones" icon={Flag}>
                <ol className="relative space-y-3 border-l border-line pl-5">
                  {project.milestones.map((m) => {
                    const overdue = !m.done && Date.parse(m.due) < Date.parse(world.now);
                    return (
                      <li key={m.id} className="relative">
                        <span className={cn("absolute top-1 -left-[25px] size-2.5 rotate-45 border-2", m.done ? "border-success bg-success" : overdue ? "border-danger bg-danger-soft" : "border-primary bg-surface")} aria-hidden />
                        <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]"><span>{m.title}</span><span className={cn("text-xs", overdue ? "text-danger" : "text-fg-subtle")}>{formatDate(m.due, true)}{m.done ? " · done" : overdue ? " · overdue" : ""}</span></div>
                        <span className="text-2xs text-fg-subtle">Phase {m.phase}: {phaseDef(m.phase).short}</span>
                      </li>
                    );
                  })}
                </ol>
              </Panel>
              <Panel title="Recent changes" icon={History} flush>
                {activity.length === 0 ? <EmptyState title="No recent activity" /> : (
                  <ul className="divide-y divide-line">{activity.slice(0, 8).map((a) => <li key={a.id} className="px-4 py-2.5 text-[13px]">{a.text}<span className="block text-2xs text-fg-subtle">{relative(a.at, world.now)}</span></li>)}</ul>
                )}
              </Panel>
            </div>
            <div className="space-y-5">
              <Panel title="Outstanding approvals and decisions" icon={Hand} flush>
                {open.length === 0 ? <EmptyState title="Nothing waiting for people" /> : (
                  <ul className="divide-y divide-line">{open.map((d) => (
                    <li key={d.id}><Link to={`/decisions?id=${d.id}`} className="flex items-center gap-2 px-4 py-2.5 hover:bg-surface-2">
                      <StatusPill size="sm" meta={PRIORITY[d.priority]} /><span className="min-w-0 flex-1 text-[13px]">{d.title}<span className="block text-2xs text-fg-subtle">{d.code} · needs {d.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")} · due {relative(d.deadline, world.now)}</span></span>
                    </Link></li>
                  ))}</ul>
                )}
              </Panel>
              <Panel title="Assigned agents" icon={Users} flush>
                <ul className="divide-y divide-line">{agents.map((a) => (
                  <li key={a.id}><Link to={`/agents?agent=${a.id}`} className="flex items-center gap-2.5 px-4 py-2 hover:bg-surface-2"><Avatar name={a.name} agent size="sm" /><span className="flex-1 text-[13px]">{a.name}</span><StatusPill size="sm" meta={AGENT_STATUS[a.status]} /></Link></li>
                ))}</ul>
              </Panel>
              <Panel title="Risks" icon={ShieldCheck} flush>
                {risks.length === 0 ? <EmptyState title="No risks recorded" /> : (
                  <ul className="divide-y divide-line">{risks.map((r) => <li key={r.id} className="flex items-center gap-2 px-4 py-2 text-[13px]"><Tag tone={riskScore(r) >= 16 ? "danger" : riskScore(r) >= 12 ? "warning" : "primary"}>{r.code}</Tag><span className="flex-1">{r.title}</span><StatusPill size="sm" meta={RISK_STATUS[r.status]} /></li>)}</ul>
                )}
              </Panel>
            </div>
          </div>
        </TabPanel>

        <TabPanel value="lifecycle">
          <div className="space-y-5">
            <Panel title="Lifecycle" subtitle="Select a phase to see it for this project" icon={CalendarClock}><LifecycleRail world={world} project={project} selected={phase} onSelect={setPhase} /></Panel>
            <PhaseContent world={world} project={project} phase={phase} />
          </div>
        </TabPanel>

        <TabPanel value="agents">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((a) => {
              const task = byId(world.tasks, a.taskId);
              return (
                <Link key={a.id} to={`/agents?agent=${a.id}`} className="rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel hover:bg-surface-2">
                  <div className="flex items-center gap-2.5"><Avatar name={a.name} agent /><span className="flex-1 font-medium">{a.name}</span></div>
                  <StatusPill size="sm" className="mt-2" meta={AGENT_STATUS[a.status]} />
                  <p className="mt-2 text-xs text-fg-muted">{task && task.projectId === project.id ? `${task.key} ${task.title}` : "Worked on this project earlier"}</p>
                  <p className="mt-1 text-2xs text-fg-subtle">{tasks.filter((t) => t.agentId === a.id).length} task(s) on this project</p>
                </Link>
              );
            })}
          </div>
        </TabPanel>

        <TabPanel value="tasks">
          <Panel flush>
            <DataTable<Task>
              rows={tasks}
              rowKey={(t) => t.id}
              columns={[
                { key: "key", header: "Task", sortValue: (t) => t.key, render: (t) => <div className="min-w-56"><span className="font-medium">{t.key}</span> {t.title}</div> },
                { key: "phase", header: "Phase", sortValue: (t) => t.phase, render: (t) => <span className="whitespace-nowrap text-xs">{t.phase}. {phaseDef(t.phase).short}</span> },
                { key: "agent", header: "Agent", hideBelow: "lg", render: (t) => <span className="text-xs">{t.agentId ? byId(world.agents, t.agentId)?.name : "People"}</span> },
                { key: "deps", header: "After", hideBelow: "xl", render: (t) => <span className="text-xs text-fg-subtle">{t.dependsOn.map((d) => byId(world.tasks, d)?.key).join(", ") || "-"}</span> },
                { key: "priority", header: "Priority", sortValue: (t) => t.priority, render: (t) => <StatusPill size="sm" meta={PRIORITY[t.priority]} /> },
                { key: "state", header: "State", sortValue: (t) => t.state, render: (t) => <StatusPill size="sm" meta={TASK_STATE[t.state]} /> },
              ]}
            />
          </Panel>
        </TabPanel>

        {Object.entries(PHASE_TABS).map(([value, n]) => (
          <TabPanel key={value} value={value}><PhaseContent world={world} project={project} phase={n} /></TabPanel>
        ))}

        <TabPanel value="decisions">
          <Panel flush>{decisions.length === 0 ? <EmptyState title="No decisions for this project" /> : (
            <ul className="divide-y divide-line">{decisions.map((d) => (
              <li key={d.id}><Link to={`/decisions?id=${d.id}`} className="flex items-center gap-2 px-4 py-2.5 hover:bg-surface-2">
                <Tag>{d.code}</Tag><span className="min-w-0 flex-1 text-[13px]">{d.title}<span className="block text-2xs text-fg-subtle">Phase {d.phase} · {byId(world.agents, d.originAgentId)?.name}{d.outcome ? ` · decided by ${actorName(world, d.outcome.by)}` : ""}</span></span>
                <StatusPill size="sm" meta={DECISION_STATUS[d.status]} />
              </Link></li>
            ))}</ul>
          )}</Panel>
        </TabPanel>

        <TabPanel value="risks">
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Risks" icon={ShieldCheck} flush>{risks.length === 0 ? <EmptyState title="No risks" /> : (
              <ul className="divide-y divide-line">{risks.map((r) => (
                <li key={r.id} className="px-4 py-2.5 text-[13px]">
                  <div className="flex items-center gap-2"><Tag tone={riskScore(r) >= 16 ? "danger" : riskScore(r) >= 12 ? "warning" : "primary"}>{r.code} · score {riskScore(r)}</Tag><span className="flex-1">{r.title}</span><StatusPill size="sm" meta={RISK_STATUS[r.status]} /></div>
                  <p className="mt-1 text-2xs text-fg-subtle">Mitigation: {r.mitigation} · owner {actorName(world, r.ownerId)} · detected by {actorName(world, r.detectedBy)}</p>
                </li>
              ))}</ul>
            )}</Panel>
            <Panel title="Issues and incidents" icon={ShieldCheck} flush>{incidents.length === 0 ? <EmptyState title="No incidents" /> : (
              <ul className="divide-y divide-line">{incidents.map((i) => (
                <li key={i.id}><Link to={`/owner?incident=${i.id}`} className="block px-4 py-2.5 text-[13px] hover:bg-surface-2">
                  <div className="flex items-center gap-2"><Tag>{i.code}</Tag><span className="flex-1">{i.title}</span><StatusPill size="sm" meta={INCIDENT_STATUS[i.status]} /></div>
                  <p className="mt-1 text-2xs text-fg-subtle">Probable cause (hypothesis, {i.rca.confidence} confidence): {i.rca.hypothesis}</p>
                </Link></li>
              ))}</ul>
            )}</Panel>
          </div>
        </TabPanel>

        <TabPanel value="documents">
          <Panel flush>{docs.length === 0 ? <EmptyState title="No documents" /> : (
            <ul className="divide-y divide-line">{docs.map((d) => { const v = latestVersion(d); return (
              <li key={d.id}><Link to={`/knowledge?doc=${d.id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2">
                <FileText className="size-4 text-fg-subtle" aria-hidden />
                <span className="min-w-0 flex-1 text-[13px]">{d.title} <span className="text-fg-subtle">v{v.no}</span><span className="block text-2xs text-fg-subtle">Phase {d.phase} · {d.sourceAgentId ? `drafted by ${actorName(world, d.sourceAgentId)}` : "by people"} · {relative(v.at, world.now)} · {d.versions.length} version(s)</span></span>
                <StatusPill size="sm" meta={ARTIFACT_STATUS[v.status]} />
              </Link></li>
            ); })}</ul>
          )}</Panel>
        </TabPanel>

        <TabPanel value="reports">
          <Panel><EmptyState icon={FileText} title="Project reports arrive in Stage 6" hint="The executive summary and the detailed report for this project, built only from these records, with preview and export." action={<Link to="/reports" className="text-[13px] text-primary-strong hover:underline">Reports and Analytics</Link>} /></Panel>
        </TabPanel>
      </Tabs>
    </div>
  );
}
