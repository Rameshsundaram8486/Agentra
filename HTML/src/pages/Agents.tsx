/* S08 Agent Control Center, the Agent Directory and the Agent Execution History. Agents open their profile and runs
   open the execution drawer, from any of the three (?agent=<id>, ?run=<id>). */
import { useMemo, useState } from "react";
import { Search, Terminal, Users, Workflow } from "lucide-react";
import { useSearchParams } from "react-router";
import { AgentProfile } from "@/components/agents/AgentProfile";
import { ExecutionDrawer, LogConsole } from "@/components/agents/ExecutionDrawer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { AGENT_STATUS, EXECUTION_STATUS, TONE_DOT } from "@/components/ui/status";
import { Tabs } from "@/components/ui/Tabs";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { PHASES } from "@/data/lifecycle";
import { duration, number, relative } from "@/lib/format";
import { currentRun, executionSeconds, successRate } from "@/store/operations";
import { agentType, agentStatusCounts, byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Agent, AgentCategory, AgentStatus, Execution, World } from "@/types";

/** The agent and run drawers, driven by the address so any page can link to them. */
function useDrawers() {
  const [params, setParams] = useSearchParams();
  const set = (key: string, value: string | null) =>
    setParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
      return p;
    });
  return {
    agentId: params.get("agent"),
    runId: params.get("run"),
    openAgent: (id: string) => set("agent", id),
    openRun: (id: string) => set("run", id),
    drawers: (
      <>
        <AgentProfile agentId={params.get("agent")} onClose={() => set("agent", null)} onOpenRun={(id) => set("run", id)} />
        <ExecutionDrawer executionId={params.get("run")} onClose={() => set("run", null)} />
      </>
    ),
  };
}

function SearchBox({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] sm:w-72">
      <Search className="size-4 text-fg-subtle" aria-hidden />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={label} aria-label={label} className="min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-subtle" />
    </label>
  );
}

function matches(world: World, agent: Agent, query: string): boolean {
  const type = agentType(world, agent.typeKey);
  const project = byId(world.projects, agent.projectId);
  return `${agent.name} ${type?.description} ${CATEGORY_LABELS[type?.category ?? "governance"]} ${project?.name ?? ""}`.toLowerCase().includes(query.toLowerCase().trim());
}

function AgentCard({ world, agent, onOpen }: { world: World; agent: Agent; onOpen: () => void }) {
  const type = agentType(world, agent.typeKey)!;
  const run = currentRun(world, agent.id);
  const task = byId(world.tasks, agent.taskId);
  const project = byId(world.projects, agent.projectId);
  return (
    <button type="button" onClick={onOpen} className="flex min-w-0 flex-col rounded-[var(--radius-panel)] border border-line bg-surface p-4 text-left shadow-panel transition-colors hover:border-line-strong hover:bg-surface-2">
      <div className="flex items-start gap-3">
        <Avatar name={agent.name} agent />
        <div className="min-w-0 flex-1">
          <div className="font-medium leading-tight">{agent.name}</div>
          <div className="mt-0.5 truncate text-2xs text-fg-subtle">{CATEGORY_LABELS[type.category].replace(/s$/, "")}</div>
        </div>
      </div>
      <StatusPill size="sm" meta={AGENT_STATUS[agent.status]} className="mt-3 self-start" />
      <p className="mt-2 line-clamp-2 min-h-10 text-xs text-fg-muted">{run ? run.title : task ? `${task.key} ${task.title}` : type.description}</p>
      <div className="mt-2 truncate text-2xs text-fg-subtle">{project ? project.name : "Company-wide"} · {relative(agent.since, world.now)}</div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3 text-center">
        <div><div className="text-[13px] font-semibold tabular">{successRate(agent)}%</div><div className="text-[10px] text-fg-subtle">success</div></div>
        <div><div className="text-[13px] font-semibold tabular">{duration(agent.avgSeconds)}</div><div className="text-[10px] text-fg-subtle">avg run</div></div>
        <div><div className="text-[13px] font-semibold tabular">{number(agent.runs)}</div><div className="text-[10px] text-fg-subtle">runs</div></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        <Tag>{type.model}</Tag>
        <Tag tone="violet">{type.autonomy}</Tag>
        {!type.inMvp && <Tag tone="warning">Preview</Tag>}
      </div>
    </button>
  );
}

const CATEGORIES = Object.keys(CATEGORY_LABELS) as AgentCategory[];
const STATUS_ORDER: AgentStatus[] = ["working", "waiting_approval", "blocked", "failed", "completed", "idle"];

export function AgentControlCenter() {
  const world = useDemo((s) => s.world);
  const { openAgent, drawers } = useDrawers();
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState<AgentStatus | "all">("all");
  const [query, setQuery] = useState("");
  const counts = agentStatusCounts(world);
  const shown = world.agents.filter(
    (a) => (category === "all" || agentType(world, a.typeKey)?.category === category) && (status === "all" || a.status === status) && matches(world, a, query),
  );
  const console = useMemo(
    () =>
      world.executions
        .filter((e) => e.status === "running" || e.status === "retrying")
        .flatMap((e) => e.logs.map((l) => ({ ...l, source: `${byId(world.agents, e.agentId)?.name ?? e.agentId}` })))
        .sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
        .slice(-40),
    [world],
  );

  return (
    <div className="space-y-5">
      <PageHeader title="Agent Control Center" crumbs={[{ label: "AI workforce" }]}
        description={`The AI workforce: ${world.agents.length} agents in ${CATEGORIES.length} categories, each with defined tools, an autonomy level and a model. Agents recommend; people decide.`} />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
        <button type="button" onClick={() => setStatus("all")} aria-pressed={status === "all"} className={cn("h-8 rounded-full border px-3 text-xs", status === "all" ? "border-primary bg-primary-soft text-fg" : "border-line text-fg-muted hover:bg-surface-2")}>All {world.agents.length}</button>
        {STATUS_ORDER.map((s) => (
          <button key={s} type="button" onClick={() => setStatus(status === s ? "all" : s)} aria-pressed={status === s}
            className={cn("inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs", status === s ? "border-primary bg-primary-soft text-fg" : "border-line text-fg-muted hover:bg-surface-2")}>
            <span className={cn("size-2 rounded-full", TONE_DOT[AGENT_STATUS[s].tone])} aria-hidden />{AGENT_STATUS[s].label} <span className="tabular">{counts[s]}</span>
          </button>
        ))}
        <div className="ml-auto w-full sm:w-auto"><SearchBox value={query} onChange={setQuery} label="Search agents" /></div>
      </div>

      <Tabs value={category} onValueChange={setCategory}
        items={[{ value: "all", label: "All agents", count: world.agents.length }, ...CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABELS[c].replace(" agents", ""), count: world.agents.filter((a) => agentType(world, a.typeKey)?.category === c).length }))]}>
        <div className="pt-4">
          {shown.length === 0 ? <EmptyState title="No agents match" hint="Change the filters or the search." /> : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {shown.map((agent) => <AgentCard key={agent.id} world={world} agent={agent} onOpen={() => openAgent(agent.id)} />)}
            </div>
          )}
        </div>
      </Tabs>

      <Panel title="Agent activity console" subtitle="Live log lines from every running agent (simulated)" icon={Terminal}>
        {console.length ? <LogConsole lines={console} live={world.sim.running} className="max-h-80" /> : <EmptyState title="No agent is running right now" />}
      </Panel>
      {drawers}
    </div>
  );
}

export function AgentDirectory() {
  const world = useDemo((s) => s.world);
  const { openAgent, agentId, drawers } = useDrawers();
  const [query, setQuery] = useState("");
  const rows = world.agents.filter((a) => matches(world, a, query));
  return (
    <div className="space-y-5">
      <PageHeader title="Agent Directory" crumbs={[{ label: "AI workforce" }]} description="Every agent, its category, the phases it works in, its model, its autonomy level and its tools."
        actions={<SearchBox value={query} onChange={setQuery} label="Search agents" />} />
      <Panel title={`${rows.length} agents`} icon={Users} flush>
        <DataTable<Agent>
          rows={rows}
          rowKey={(a) => a.id}
          onRowClick={(a) => openAgent(a.id)}
          selectedKey={agentId ?? undefined}
          columns={[
            { key: "name", header: "Agent", sortValue: (a) => a.name, render: (a) => <span className="flex items-center gap-2"><Avatar name={a.name} agent size="sm" /><span className="font-medium">{a.name}</span></span> },
            { key: "category", header: "Category", sortValue: (a) => agentType(world, a.typeKey)!.category, render: (a) => CATEGORY_LABELS[agentType(world, a.typeKey)!.category].replace(" agents", "") },
            { key: "phases", header: "Phases", hideBelow: "lg", render: (a) => { const t = agentType(world, a.typeKey)!; return <span className="text-xs text-fg-muted">{t.phases.length ? t.phases.map((n) => PHASES[n - 1]!.short).join(", ") : "Company-wide"}</span>; } },
            { key: "model", header: "Model", hideBelow: "xl", render: (a) => <span className="text-xs">{agentType(world, a.typeKey)!.model} · {agentType(world, a.typeKey)!.effort}</span> },
            { key: "autonomy", header: "Autonomy", sortValue: (a) => agentType(world, a.typeKey)!.autonomy, render: (a) => <Tag tone="violet">{agentType(world, a.typeKey)!.autonomy}</Tag> },
            { key: "tools", header: "Tools", align: "right", hideBelow: "md", render: (a) => agentType(world, a.typeKey)!.tools.length },
            { key: "scope", header: "Scope", hideBelow: "md", render: (a) => (agentType(world, a.typeKey)!.inMvp ? <Tag tone="primary">MVP</Tag> : <Tag tone="warning">Preview</Tag>) },
            { key: "status", header: "Status", sortValue: (a) => a.status, render: (a) => <StatusPill size="sm" meta={AGENT_STATUS[a.status]} /> },
            { key: "success", header: "Success", align: "right", sortValue: successRate, render: (a) => `${successRate(a)}%` },
          ]}
        />
      </Panel>
      {drawers}
    </div>
  );
}

export function ExecutionHistory() {
  const world = useDemo((s) => s.world);
  const { openRun, runId, drawers } = useDrawers();
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const rows = world.executions
    .filter((e) => (status === "all" || e.status === status) && `${e.title} ${byId(world.agents, e.agentId)?.name} ${byId(world.projects, e.projectId)?.name ?? ""}`.toLowerCase().includes(query.toLowerCase().trim()))
    .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  return (
    <div className="space-y-5">
      <PageHeader title="Agent Execution History" crumbs={[{ label: "AI workforce" }]} description="Every agent run with its inputs, output, logs, cost and outcome."
        actions={<SearchBox value={query} onChange={setQuery} label="Search runs" />} />
      <Tabs value={status} onValueChange={setStatus}
        items={[{ value: "all", label: "All", count: world.executions.length }, ...(["running", "succeeded", "failed", "paused"] as const).map((s) => ({ value: s, label: EXECUTION_STATUS[s].label, count: world.executions.filter((e) => e.status === s).length }))]}>
        <div className="pt-4">
          <Panel title={`${rows.length} runs`} icon={Workflow} flush>
            <DataTable<Execution>
              rows={rows}
              rowKey={(e) => e.id}
              onRowClick={(e) => openRun(e.id)}
              selectedKey={runId ?? undefined}
              empty="No runs match"
              columns={[
                { key: "started", header: "Started", sortValue: (e) => e.startedAt, render: (e) => <span className="whitespace-nowrap text-xs text-fg-muted">{relative(e.startedAt, world.now)}</span> },
                { key: "agent", header: "Agent", sortValue: (e) => byId(world.agents, e.agentId)?.name ?? "", render: (e) => <span className="flex items-center gap-2 whitespace-nowrap"><Avatar name={byId(world.agents, e.agentId)?.name ?? ""} agent size="sm" />{byId(world.agents, e.agentId)?.name}</span> },
                { key: "title", header: "Activity", render: (e) => <div className="min-w-48"><div>{e.title}</div><div className="text-2xs text-fg-subtle">{byId(world.projects, e.projectId)?.name ?? "Company-wide"}</div></div> },
                { key: "duration", header: "Duration", align: "right", sortValue: (e) => executionSeconds(e, world.now), render: (e) => duration(executionSeconds(e, world.now)) },
                { key: "cost", header: "Cost", align: "right", hideBelow: "lg", sortValue: (e) => e.costUsd, render: (e) => `$${e.costUsd.toFixed(2)}` },
                { key: "status", header: "Status", sortValue: (e) => e.status, render: (e) => <StatusPill size="sm" meta={EXECUTION_STATUS[e.status]} /> },
              ]}
            />
          </Panel>
        </div>
      </Tabs>
      {drawers}
    </div>
  );
}
