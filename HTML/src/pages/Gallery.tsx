/* Stage 1 check page: the design tokens and base components in the current theme, running on the shared demo data
   and the simulation. The application shell (Stage 2) replaces this as the landing page. */
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  Activity, Bot, CircleCheck, FolderKanban, Gauge, Pause, Play, RotateCcw, Scale, ShieldExclamationPoint, Timer, TriangleExclamationPoint,
} from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { CountBadge, Dot, StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Dialog, Drawer, Tooltip } from "@/components/ui/Overlays";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState, ErrorState, Progress, Skeleton } from "@/components/ui/States";
import {
  AGENT_STATUS, DECISION_STATUS, EXECUTION_STATUS, HEALTH, PHASE_STATE, PRIORITY, TASK_STATE, TONE_TEXT, type StatusMeta, type Tone,
} from "@/components/ui/status";
import { Segmented, TabPanel, Tabs } from "@/components/ui/Tabs";
import { phaseDef } from "@/data/lifecycle";
import { formatDateTime, relative } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { DemoRuleError, ROLE_LABELS } from "@/store/actions";
import { byId, completion, currentPhase, kpis, nextMilestone, openDecisions, projectHealth } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import { scenarioProgress } from "@/simulation/engine";
import type { Project } from "@/types";

const TONES: Tone[] = ["primary", "cyan", "violet", "success", "warning", "danger", "neutral"];

function Vocabulary({ title, entries }: { title: string; entries: Record<string, StatusMeta> }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold text-fg-muted">{title}</h3>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(entries).map(([key, meta]) => <StatusPill key={key} meta={meta} />)}
      </div>
    </div>
  );
}

export function Gallery() {
  const world = useDemo((s) => s.world);
  const { theme, role, startSimulation, pauseSimulation, setSpeed, reset } = useDemo();
  const data = useDataService();
  const [tab, setTab] = useState("projects");
  const [view, setView] = useState<"table" | "cards">("table");
  const [drawer, setDrawer] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [message, setMessage] = useState<{ tone: Tone; text: string } | null>(null);
  const figures = kpis(world);
  const progress = scenarioProgress(world);

  function accept(decisionId: string) {
    try {
      data.decide({ decisionId, action: "accept" });
      setMessage({ tone: "success", text: "Recorded. The decision history and the affected records are updated." });
    } catch (error) {
      setMessage({ tone: "danger", text: error instanceof DemoRuleError ? error.message : String(error) });
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Design system" crumbs={[{ label: "Administration" }]}
        description="The tokens, components and status vocabulary every screen uses, shown on the live demo data." />

      <Panel title="Simulation" subtitle="Scripted, deterministic events; nothing here is connected to the Agentra backend" icon={Timer}
        actions={
          <>
            <Segmented label="Simulation speed" value={String(world.sim.speed) as "1" | "2" | "5"} onChange={(v) => setSpeed(Number(v) as 1 | 2 | 5)} options={[{ value: "1", label: "1x" }, { value: "2", label: "2x" }, { value: "5", label: "5x" }]} />
            {world.sim.running ? <Button size="sm" icon={Pause} onClick={pauseSimulation}>Pause</Button> : <Button size="sm" variant="primary" icon={Play} onClick={startSimulation}>Start</Button>}
            <Button size="sm" variant="ghost" icon={RotateCcw} onClick={reset}>Reset demo</Button>
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]">
          <span className="flex items-center gap-2"><Dot tone={world.sim.running ? "success" : "neutral"} pulse={world.sim.running} />{world.sim.running ? "LIVE (simulated)" : "Paused"}</span>
          <span className="text-fg-muted">Simulated time <span className="text-fg tabular">{formatDateTime(world.now)}</span></span>
          <span className="text-fg-muted">Script <span className="text-fg tabular">{progress.fired} of {progress.total}</span> events, {progress.waiting} waiting for people or work</span>
        </div>
      </Panel>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="Key figures">
        <Kpi label="Active projects" value={figures.activeProjects} icon={FolderKanban} hint={`${world.projects.length} in the portfolio`} />
        <Kpi label="Agents working" value={figures.activeAgents} icon={Bot} tone="cyan" hint={`of ${world.agents.length} agents`} />
        <Kpi label="Tasks running" value={figures.tasksRunning} icon={Activity} tone="primary" hint={`${world.tasks.length} tasks in total`} />
        <Kpi label="Decisions waiting" value={figures.pendingDecisions} icon={Scale} tone="violet" hint={figures.overdueDecisions ? `${figures.overdueDecisions} overdue` : "none overdue"} />
        <Kpi label="Projects at risk" value={figures.projectsAtRisk} icon={TriangleExclamationPoint} tone="warning" hint="at risk or critical" />
        <Kpi label="Approved deliverables" value={figures.completedDeliverables} icon={CircleCheck} tone="success" hint={`of ${world.artifacts.length} documents`} />
      </section>

      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <Panel title="Projects" subtitle="Health, phase and completion are derived from records" icon={Gauge} flush
          actions={<Segmented label="View" value={view} onChange={setView} options={[{ value: "table", label: "Table" }, { value: "cards", label: "Cards" }]} />}
        >
          <Tabs value={tab} onValueChange={setTab} items={[{ value: "projects", label: "Portfolio", count: world.projects.length }, { value: "decisions", label: "Decisions", count: figures.pendingDecisions }]} className="px-4">
            <TabPanel value="projects" className="-mx-4 pt-0">
              {view === "table" ? (
                <DataTable<Project>
                  rows={world.projects}
                  rowKey={(p) => p.id}
                  onRowClick={() => setDrawer(true)}
                  columns={[
                    { key: "name", header: "Project", sortValue: (p) => p.name, render: (p) => <div><div className="font-medium">{p.name}</div><div className="text-xs text-fg-subtle">{byId(world.customers, p.customerId)?.name}</div></div> },
                    { key: "phase", header: "Phase", sortValue: (p) => currentPhase(p).phase, render: (p) => <span className="whitespace-nowrap text-fg-muted">{currentPhase(p).phase}. {phaseDef(currentPhase(p).phase).short}</span>, hideBelow: "md" },
                    { key: "done", header: "Complete", sortValue: completion, render: (p) => <div className="flex w-28 items-center gap-2"><Progress value={completion(p)} label={`${p.name} completion`} /><span className="text-xs tabular">{completion(p)}%</span></div> },
                    { key: "health", header: "Health", sortValue: (p) => projectHealth(world, p).health, render: (p) => <StatusPill meta={HEALTH[projectHealth(world, p).health]} /> },
                    { key: "next", header: "Next milestone", render: (p) => <span className="text-xs text-fg-muted">{nextMilestone(p)?.title ?? "None"}</span>, hideBelow: "lg" },
                    { key: "open", header: "Open decisions", align: "right", sortValue: (p) => openDecisions(world, p.id).length, render: (p) => openDecisions(world, p.id).length },
                  ]}
                />
              ) : (
                <div className="grid gap-3 p-4 sm:grid-cols-2">
                  {world.projects.map((p) => (
                    <div key={p.id} className="rounded-lg border border-line bg-surface-2 p-3">
                      <div className="flex items-start justify-between gap-2"><span className="font-medium">{p.name}</span><StatusPill size="sm" meta={HEALTH[projectHealth(world, p).health]} /></div>
                      <p className="mt-1 text-xs text-fg-subtle">{projectHealth(world, p).reasons[0]}</p>
                      <Progress className="mt-3" value={completion(p)} label={`${p.name} completion`} />
                    </div>
                  ))}
                </div>
              )}
            </TabPanel>
            <TabPanel value="decisions" className="space-y-2 pb-4">
              {message && <p role="status" className={`rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13px] ${TONE_TEXT[message.tone]}`}>{message.text}</p>}
              {openDecisions(world).map((d) => (
                <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2"><Tag>{d.code}</Tag><span className="truncate font-medium">{d.title}</span></div>
                    <div className="mt-0.5 text-xs text-fg-subtle">Needs {d.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")}; due {relative(d.deadline, world.now)}{d.blockedBy ? `; ${d.blockedBy}` : ""}</div>
                  </div>
                  <div className="flex items-center gap-2"><StatusPill size="sm" meta={PRIORITY[d.priority]} /><Button size="sm" onClick={() => accept(d.id)}>Accept recommendation</Button></div>
                </div>
              ))}
            </TabPanel>
          </Tabs>
        </Panel>

        <Panel title="Live activity" subtitle="Newest first" icon={Activity} flush actions={<CountBadge count={world.activity.length} label="events" />}>
          <ol className="max-h-[420px] divide-y divide-line overflow-y-auto">
            {world.activity.slice(0, 12).map((event) => (
              <li key={event.id} className="flex gap-2.5 px-4 py-2.5">
                <Dot tone={{ info: "primary", success: "success", warning: "warning", critical: "danger" }[event.severity] as Tone} className="mt-1.5" />
                <div className="min-w-0">
                  <p className="text-[13px] text-fg">{event.text}</p>
                  <p className="text-2xs text-fg-subtle">{relative(event.at, world.now)}{event.projectId ? ` · ${byId(world.projects, event.projectId)?.name}` : ""}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>

      <Panel title="Status vocabulary" subtitle="Every status has an icon, a label and a tone" icon={ShieldExclamationPoint}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Vocabulary title="Agents" entries={AGENT_STATUS} />
          <Vocabulary title="Project health" entries={HEALTH} />
          <Vocabulary title="Lifecycle phases" entries={PHASE_STATE} />
          <Vocabulary title="Tasks" entries={TASK_STATE} />
          <Vocabulary title="Decisions" entries={DECISION_STATUS} />
          <Vocabulary title="Agent runs" entries={EXECUTION_STATUS} />
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Tokens and controls" icon={Gauge}>
          <div className="flex flex-wrap gap-2">
            {TONES.map((tone) => <Tag key={tone} tone={tone}>{tone}</Tag>)}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button variant="primary">Primary</Button>
            <Button>Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Reject</Button>
            <Button disabled>Disabled</Button>
            <Tooltip content="Tooltips work on hover and on keyboard focus."><Button size="sm" variant="ghost">Hover or focus me</Button></Tooltip>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Avatar name="Rania Al Mansoori" /><Avatar name="Priya Nair" /><Avatar name="Developer Agent" agent /><Avatar name="QA Agent" agent size="lg" />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <Field label="Acting as">{ROLE_LABELS[role]}</Field>
            <Field label="Theme">{theme}</Field>
          </dl>
          <div className="mt-4 flex gap-2">
            <Button size="sm" onClick={() => setDrawer(true)}>Open drawer</Button>
            <Button size="sm" onClick={() => setDialog(true)}>Open dialog</Button>
          </div>
        </Panel>
        <Panel title="Empty, loading and error states" icon={Gauge}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-line"><EmptyState title="No decisions waiting" hint="New agent recommendations appear here." /></div>
            <div className="rounded-lg border border-line"><ErrorState title="Could not load the report" detail="Try again; nothing was changed." /></div>
            <div className="space-y-2 rounded-lg border border-line p-4 sm:col-span-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-16 w-full" /></div>
          </div>
        </Panel>
      </div>

      <Drawer open={drawer} onOpenChange={setDrawer} title="Project details" description="Drawers hold details without leaving the page"
        footer={<><Button onClick={() => setDrawer(false)}>Close</Button><Button variant="primary">Open workspace</Button></>}>
        <p className="text-[13px] text-fg-muted">The project workspace arrives in Stage 4. Escape or the close button dismisses this drawer, and focus returns to where it was.</p>
      </Drawer>
      <Dialog open={dialog} onOpenChange={setDialog} title="Confirm" description="Dialogs are for short, focused tasks"
        footer={<><Button onClick={() => setDialog(false)}>Cancel</Button><Button variant="primary" onClick={() => setDialog(false)}>Confirm</Button></>}>
        <p className="text-[13px] text-fg-muted">Nothing is sent anywhere: this is the demo.</p>
      </Dialog>
    </div>
  );
}
