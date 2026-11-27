/* S03 Projects (table, cards, kanban), the Project Pipeline (by phase), the Project Delivery Board (work items by
   state) and Milestones and Dependencies (timeline). Everything comes from the shared records. */
import { useMemo, useState, type ReactNode } from "react";
import { CalendarClock, CircleCheck, CirclePause, FolderKanban, GitBranch, Kanban, LayoutGrid, Search, Table, TriangleExclamationPoint } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { EmptyState, Progress } from "@/components/ui/States";
import { HEALTH, PRIORITY, TASK_STATE, TONE_DOT, TONE_SOFT } from "@/components/ui/status";
import { Segmented } from "@/components/ui/Tabs";
import { PHASES, phaseDef } from "@/data/lifecycle";
import { aed, formatDate } from "@/lib/format";
import { queues } from "@/store/operations";
import { actorName, byId, completion, currentPhase, nextMilestone, openDecisions, projectHealth } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Health, Project, Task, TaskState, World } from "@/types";

const SERVICE: Record<Project["service"], string> = {
  sharepoint_migration: "SharePoint migration", intranet: "Intranet", power_platform: "Power Platform", azure: "Azure", ai: "AI solutions", automation: "Automation",
};

function SearchBox({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] sm:w-64">
      <Search className="size-4 text-fg-subtle" aria-hidden />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={label} aria-label={label} className="min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-subtle" />
    </label>
  );
}

function Select<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as T)} aria-label={label} className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

function ProjectCard({ world, project }: { world: World; project: Project }) {
  const h = projectHealth(world, project);
  const phase = currentPhase(project);
  const milestone = nextMilestone(project);
  return (
    <Link to={`/projects/${project.id}`} className="block rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel transition-colors hover:border-line-strong hover:bg-surface-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0"><div className="font-medium">{project.name}</div><div className="text-2xs text-fg-subtle">{byId(world.customers, project.customerId)?.name} · {project.code}</div></div>
        <StatusPill size="sm" meta={HEALTH[h.health]} />
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-fg-muted">{project.summary}</p>
      <div className="mt-3 flex items-center gap-2"><Progress value={completion(project)} label={`${project.name} completion`} /><span className="text-xs tabular">{completion(project)}%</span></div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-2xs text-fg-subtle">
        <Tag>Phase {phase.phase}: {phaseDef(phase.phase).short}</Tag>
        <Tag tone="neutral">{SERVICE[project.service]}</Tag>
        {openDecisions(world, project.id).length > 0 && <Tag tone="violet">{openDecisions(world, project.id).length} decisions</Tag>}
      </div>
      <div className="mt-3 flex justify-between border-t border-line pt-2 text-2xs text-fg-subtle">
        <span>{actorName(world, project.managerId)}</span>
        <span>{milestone ? `${milestone.title}, ${formatDate(milestone.due)}` : `Target ${formatDate(project.targetDate)}`}</span>
      </div>
    </Link>
  );
}

/** Columns of cards; used by the portfolio kanban and the pipeline. */
function Board<T>({ columns, render, keyOf }: { columns: { id: string; title: ReactNode; hint?: string; items: T[]; tone?: string }[]; render: (item: T) => ReactNode; keyOf: (item: T) => string }) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {columns.map((col) => (
        <section key={col.id} aria-label={typeof col.title === "string" ? col.title : col.id} className={cn("flex w-72 shrink-0 flex-col rounded-[var(--radius-panel)] border border-line bg-surface-2/40", col.tone)}>
          <header className="flex items-center justify-between border-b border-line px-3 py-2.5">
            <div><div className="text-[13px] font-semibold">{col.title}</div>{col.hint && <div className="text-2xs text-fg-subtle">{col.hint}</div>}</div>
            <span className="rounded-full bg-surface-3 px-2 text-2xs font-semibold tabular">{col.items.length}</span>
          </header>
          <div className="flex min-h-24 flex-col gap-2 p-2">{col.items.length ? col.items.map((item) => <div key={keyOf(item)}>{render(item)}</div>) : <p className="py-4 text-center text-2xs text-fg-subtle">None</p>}</div>
        </section>
      ))}
    </div>
  );
}

const STAGES = [
  { id: "presales", title: "Pre-sales", hint: "Phases 1-5", phases: [1, 2, 3, 4, 5] },
  { id: "kickoff", title: "Kickoff", hint: "Phase 6", phases: [6] },
  { id: "requirements", title: "Requirements", hint: "Phase 7", phases: [7] },
  { id: "design", title: "Architecture", hint: "Phase 8", phases: [8] },
  { id: "development", title: "Development", hint: "Phase 9", phases: [9] },
  { id: "qa", title: "QA", hint: "Phase 10", phases: [10] },
  { id: "uat", title: "UAT", hint: "Phase 11", phases: [11] },
  { id: "release", title: "Go-live and closure", hint: "Phases 12-13", phases: [12, 13] },
];

export function Projects() {
  const world = useDemo((s) => s.world);
  const navigate = useNavigate();
  const [view, setView] = useState<"table" | "cards" | "kanban">("table");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | Project["status"]>("all");
  const [health, setHealth] = useState<"all" | Health>("all");
  const rows = world.projects.filter((p) => {
    const text = `${p.name} ${p.code} ${byId(world.customers, p.customerId)?.name} ${actorName(world, p.managerId)}`.toLowerCase();
    return (status === "all" || p.status === status) && (health === "all" || projectHealth(world, p).health === health) && text.includes(query.toLowerCase().trim());
  });
  const atRisk = world.projects.filter((p) => ["at_risk", "critical"].includes(projectHealth(world, p).health));
  const budget = world.projects.filter((p) => p.status !== "completed").reduce((n, p) => n + p.budgetAed, 0);
  const spent = world.projects.filter((p) => p.status !== "completed").reduce((n, p) => n + p.spentAed, 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Projects" crumbs={[{ label: "Project operations" }]} description="The project portfolio: health, phase, owner, customer, budget and dates. Select a project to open its workspace." />
      <section aria-label="Portfolio summary" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Kpi label="Active" value={world.projects.filter((p) => p.status === "active").length} icon={FolderKanban} onClick={() => setStatus("active")} />
        <Kpi label="At risk or critical" value={atRisk.length} icon={TriangleExclamationPoint} tone="warning" hint={atRisk.map((p) => p.code).join(", ")} />
        <Kpi label="On hold" value={world.projects.filter((p) => p.status === "on_hold").length} icon={CirclePause} tone="neutral" onClick={() => setStatus("on_hold")} />
        <Kpi label="Completed" value={world.projects.filter((p) => p.status === "completed").length} icon={CircleCheck} tone="success" onClick={() => setStatus("completed")} />
        <Kpi label="Budget used (open projects)" value={`${Math.round((spent / budget) * 100)}%`} icon={CalendarClock} tone="cyan" hint={`${aed(spent)} of ${aed(budget)}`} />
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <SearchBox value={query} onChange={setQuery} label="Search projects" />
        <Select label="Status" value={status} onChange={setStatus} options={[["all", "All statuses"], ["active", "Active"], ["on_hold", "On hold"], ["completed", "Completed"]]} />
        <Select label="Health" value={health} onChange={setHealth} options={[["all", "Any health"], ...(Object.keys(HEALTH) as Health[]).map((h) => [h, HEALTH[h].label] as [Health, string])]} />
        <div className="ml-auto">
          <Segmented label="View" value={view} onChange={setView} options={[{ value: "table", label: <><Table className="size-3.5" />Table</> }, { value: "cards", label: <><LayoutGrid className="size-3.5" />Cards</> }, { value: "kanban", label: <><Kanban className="size-3.5" />Kanban</> }]} />
        </div>
      </div>

      {rows.length === 0 ? <Panel><EmptyState title="No projects match" hint="Change the search or the filters." /></Panel> : view === "table" ? (
        <Panel flush>
          <DataTable<Project>
            rows={rows}
            rowKey={(p) => p.id}
            onRowClick={(p) => navigate(`/projects/${p.id}`)}
            columns={[
              { key: "name", header: "Project", sortValue: (p) => p.name, render: (p) => <div className="min-w-48"><div className="font-medium">{p.name}</div><div className="text-2xs text-fg-subtle">{byId(world.customers, p.customerId)?.name} · {p.code}</div></div> },
              { key: "owner", header: "Owner", hideBelow: "xl", sortValue: (p) => actorName(world, p.managerId), render: (p) => <span className="flex items-center gap-2 whitespace-nowrap text-xs"><Avatar name={actorName(world, p.managerId)} size="sm" />{actorName(world, p.managerId)}</span> },
              { key: "phase", header: "Phase", sortValue: (p) => currentPhase(p).phase, render: (p) => <span className="whitespace-nowrap text-xs">{currentPhase(p).phase}. {phaseDef(currentPhase(p).phase).short}</span> },
              { key: "complete", header: "Complete", sortValue: completion, render: (p) => <div className="flex w-24 items-center gap-2"><Progress value={completion(p)} label={`${p.name} completion`} /><span className="text-xs tabular">{completion(p)}%</span></div> },
              { key: "health", header: "Health", sortValue: (p) => projectHealth(world, p).health, render: (p) => <StatusPill size="sm" meta={HEALTH[projectHealth(world, p).health]} /> },
              { key: "budget", header: "Budget used", align: "right", hideBelow: "lg", sortValue: (p) => p.spentAed / p.budgetAed, render: (p) => <span className="whitespace-nowrap text-xs">{Math.round((p.spentAed / p.budgetAed) * 100)}% <span className="text-fg-subtle">of {aed(p.budgetAed)}</span></span> },
              { key: "start", header: "Start", hideBelow: "2xl", sortValue: (p) => p.startDate, render: (p) => <span className="text-xs">{formatDate(p.startDate)}</span> },
              { key: "target", header: "Target", hideBelow: "md", sortValue: (p) => p.targetDate, render: (p) => <span className="whitespace-nowrap text-xs">{formatDate(p.targetDate, true)}</span> },
            ]}
          />
        </Panel>
      ) : view === "cards" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map((p) => <ProjectCard key={p.id} world={world} project={p} />)}</div>
      ) : (
        <Board<Project>
          keyOf={(p) => p.id}
          render={(p) => <ProjectCard world={world} project={p} />}
          columns={STAGES.map((s) => ({ id: s.id, title: s.title, hint: s.hint, items: rows.filter((p) => s.phases.includes(p.status === "completed" ? 13 : currentPhase(p).phase)), tone: [7, 8, 9, 10, 11].includes(s.phases[0]!) ? "border-primary/25" : undefined }))}
        />
      )}
      <p className="text-2xs text-fg-subtle">Budget figures are sample data for the demo.</p>
    </div>
  );
}

export function Pipeline() {
  const world = useDemo((s) => s.world);
  return (
    <div className="space-y-5">
      <PageHeader title="Project Pipeline" crumbs={[{ label: "Project operations" }]} description="Every project at its current phase, from sales to closure. Phases 7 to 11 are the MVP; the others are previews." />
      <Board<Project>
        keyOf={(p) => p.id}
        render={(p) => <ProjectCard world={world} project={p} />}
        columns={PHASES.map((ph) => ({
          id: String(ph.number),
          title: `${ph.number}. ${ph.short}`,
          hint: ph.mvp ? "MVP" : "Preview",
          items: world.projects.filter((p) => (p.status === "completed" ? 13 : currentPhase(p).phase) === ph.number),
          tone: ph.mvp ? "border-primary/25" : undefined,
        }))}
      />
    </div>
  );
}

// "Waiting on other work" and "Ready" use the same rule as Live Operations (store/operations.ts queues).
const BOARD_COLUMNS: { id: string; title: string; states: TaskState[] }[] = [
  { id: "todo", title: "Waiting on other work", states: [] },
  { id: "ready", title: "Ready to start", states: [] },
  { id: "doing", title: "In progress", states: ["in_progress"] },
  { id: "people", title: "Waiting for people", states: ["waiting_for_review", "waiting_for_input", "changes_requested"] },
  { id: "stuck", title: "Blocked or failed", states: ["blocked", "failed"] },
  { id: "done", title: "Done", states: ["completed"] },
];

export function DeliveryBoard() {
  const world = useDemo((s) => s.world);
  const [project, setProject] = useState("all");
  const tasks = world.tasks.filter((t) => t.state !== "cancelled" && (project === "all" || t.projectId === project));
  const q = queues(world);
  const inColumn = (id: string, t: Task) =>
    id === "todo" ? q.waitingOnWork.includes(t) : id === "ready" ? q.ready.includes(t) : BOARD_COLUMNS.find((c) => c.id === id)!.states.includes(t.state);
  return (
    <div className="space-y-5">
      <PageHeader title="Project Delivery Board" crumbs={[{ label: "Project operations" }]} description="Work items across projects by workflow state. States change only through the workflow engine."
        actions={<Select label="Project" value={project} onChange={setProject} options={[["all", "All projects"], ...world.projects.map((p) => [p.id, p.name] as [string, string])]} />} />
      <Board<Task>
        keyOf={(t) => t.id}
        render={(t) => (
          <Link to={`/projects/${t.projectId}?tab=tasks`} className="block rounded-lg border border-line bg-surface p-2.5 hover:border-line-strong">
            <div className="flex items-center justify-between gap-2"><Tag>{t.key}</Tag><StatusPill size="sm" meta={PRIORITY[t.priority]} /></div>
            <p className="mt-1.5 text-xs">{t.title}</p>
            <div className="mt-1.5 flex items-center justify-between text-2xs text-fg-subtle">
              <span className="truncate">{byId(world.projects, t.projectId)?.code} · Phase {t.phase}</span>
              {t.agentId && <span className="flex items-center gap-1"><Avatar name={actorName(world, t.agentId)} agent size="sm" /></span>}
            </div>
            {BOARD_COLUMNS.find((c) => c.id === "people")!.states.includes(t.state) && <StatusPill size="sm" className="mt-1.5" meta={TASK_STATE[t.state]} />}
          </Link>
        )}
        columns={BOARD_COLUMNS.map((c) => ({ id: c.id, title: c.title, items: tasks.filter((t) => inColumn(c.id, t)) }))}
      />
    </div>
  );
}

const DAY = 86_400_000;

export function Milestones() {
  const world = useDemo((s) => s.world);
  const now = Date.parse(world.now);
  const start = now - 45 * DAY;
  const end = now + 60 * DAY;
  const x = (iso: string) => Math.min(100, Math.max(0, ((Date.parse(iso) - start) / (end - start)) * 100));
  // Seven date labels; the right edge has none, so no label is cut off.
  const ticks = useMemo(() => Array.from({ length: 7 }, (_, i) => new Date(start + (i * (end - start)) / 7).toISOString()), [start, end]);
  const chains = world.tasks.filter((t) => t.dependsOn.length > 0 && t.state !== "completed" && t.state !== "cancelled");
  return (
    <div className="space-y-5">
      <PageHeader title="Milestones and Dependencies" crumbs={[{ label: "Project operations" }]} description="Milestones across projects on one timeline, and the dependencies between open work items." />
      <Panel title="Milestone timeline" subtitle="45 days back to 60 days ahead (simulated today)" icon={CalendarClock}>
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <div className="relative ml-56 h-6 border-b border-line text-2xs text-fg-subtle">
              {ticks.map((t) => <span key={t} className="absolute -translate-x-1/2" style={{ left: `${x(t)}%` }}>{formatDate(t)}</span>)}
            </div>
            {world.projects.filter((p) => p.status !== "completed").map((p) => {
              const h = projectHealth(world, p).health;
              return (
                <div key={p.id} className="flex items-center border-b border-line py-2 last:border-0">
                  <Link to={`/projects/${p.id}`} className="w-56 shrink-0 pr-3 text-[13px] hover:text-primary-strong"><span className="block truncate">{p.name}</span><StatusPill size="sm" meta={HEALTH[h]} /></Link>
                  <div className="relative h-10 flex-1">
                    <div className="absolute top-1/2 h-0.5 w-full -translate-y-1/2 bg-surface-3" />
                    <span aria-hidden className="absolute inset-y-0 w-px bg-cyan/70" style={{ left: `${x(world.now)}%` }} />
                    <div className={cn("absolute top-1/2 h-1 -translate-y-1/2 rounded-full", TONE_DOT[HEALTH[h].tone])} style={{ left: `${x(p.startDate)}%`, width: `${Math.max(1, x(p.targetDate) - x(p.startDate))}%`, opacity: 0.35 }} />
                    {p.milestones.map((m) => (
                      <span key={m.id} title={`${m.title}: ${formatDate(m.due, true)}${m.done ? " (done)" : Date.parse(m.due) < now ? " (overdue)" : ""}`}
                        className={cn("absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border-2", m.done ? "border-success bg-success" : Date.parse(m.due) < now ? "border-danger bg-danger-soft" : "border-primary bg-surface")}
                        style={{ left: `${x(m.due)}%` }} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-2xs text-fg-subtle">
          <span className="flex items-center gap-1.5"><span className="size-2.5 rotate-45 border-2 border-success bg-success" />Done</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rotate-45 border-2 border-primary" />Upcoming</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rotate-45 border-2 border-danger bg-danger-soft" />Overdue</span>
          <span className="flex items-center gap-1.5"><span className="h-3 w-px bg-cyan" />Today (simulated)</span>
        </div>
      </Panel>
      <Panel title="Dependencies" subtitle="Open work items and what they wait for" icon={GitBranch} flush>
        <ul className="divide-y divide-line">
          {chains.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-xs">
              {t.dependsOn.map((d) => { const dep = byId(world.tasks, d)!; return <span key={d} className={cn("rounded-md px-1.5 py-0.5", TONE_SOFT[TASK_STATE[dep.state].tone])}>{dep.key}</span>; })}
              <span className="text-fg-subtle">→</span>
              <span className="font-medium">{t.key}</span><span className="min-w-0 flex-1 truncate">{t.title}</span>
              <span className="text-fg-subtle">{byId(world.projects, t.projectId)?.code}</span>
              <StatusPill size="sm" meta={TASK_STATE[t.state]} />
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
