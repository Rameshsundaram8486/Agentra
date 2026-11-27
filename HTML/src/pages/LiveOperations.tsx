/* S02 Live Operations: workflow runs in flight, agent handoffs, queues, human dependencies, failures, retries and
   bottlenecks. Selecting a stage, gate or run shows its details; controls are simulated and role-checked. */
import { useState } from "react";
import { Activity, CircleX, Clock, Hand, Hourglass, Layers, RotateCcw, Waypoints } from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { ExecutionDrawer } from "@/components/agents/ExecutionDrawer";
import { PageHeader } from "@/components/layout/PageHeader";
import { PIPELINE, PipelineGraph } from "@/components/workflows/PipelineGraph";
import { Avatar } from "@/components/ui/Avatar";
import { Dot, StatusPill, Tag } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { AGENT_STATUS, EXECUTION_STATUS, PRIORITY, TASK_STATE } from "@/components/ui/status";
import { Segmented } from "@/components/ui/Tabs";
import { duration, formatDateTime, relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import { bottlenecks, currentRun, decisionsFor, executionSeconds, gateDecisions, IN_FLIGHT, queues } from "@/store/operations";
import { agentType, byId } from "@/store/selectors";
import { briefing } from "@/store/briefing";
import { useDemo } from "@/store/useDemo";
import type { Execution, World } from "@/types";

function SelectionDetail({ world, selected, onOpenRun }: { world: World; selected: string; onOpenRun: (id: string) => void }) {
  if (selected.startsWith("gate-")) {
    const phase = Number(selected.slice(5));
    const stage = PIPELINE.find((p) => p.phase === phase)!;
    const waiting = gateDecisions(world, phase);
    return (
      <div className="space-y-3">
        <div><p className="text-sm font-semibold">{stage.gate} gate</p><p className="text-xs text-fg-subtle">Phase {phase}: only people decide here; agents never approve.</p></div>
        {waiting.length === 0 ? <p className="text-[13px] text-fg-muted">Nothing is waiting at this gate.</p> : (
          <ul className="space-y-1.5">
            {waiting.map((d) => (
              <li key={d.id}>
                <Link to={`/decisions?id=${d.id}`} className="block rounded-lg border border-line px-3 py-2 hover:bg-surface-2">
                  <span className="flex items-center gap-2"><StatusPill size="sm" meta={PRIORITY[d.priority]} /><span className="text-[13px] font-medium">{d.code}</span></span>
                  <span className="mt-0.5 block text-xs">{d.title}</span>
                  <span className="block text-2xs text-fg-subtle">needs {d.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")} · due {relative(d.deadline, world.now)}{d.blockedBy ? ` · waiting: ${d.blockedBy}` : ""}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  if (selected === "project_owner") {
    const brief = briefing(world);
    return (
      <div className="space-y-3">
        <div><p className="text-sm font-semibold">Project Owner Agent</p><p className="text-xs text-fg-subtle">Watches every stage for delays, stuck work, failed runs and overdue decisions.</p></div>
        <p className="text-[13px]">{brief.headline}</p>
        <ul className="space-y-1">{brief.findings.slice(0, 5).map((f) => <li key={f.text}><Link to={f.link} className="block rounded-md px-1.5 py-1 text-xs hover:bg-surface-2">{f.text}</Link></li>)}</ul>
        <Link to="/owner" className="text-xs text-primary-strong hover:underline">Open the Project Owner workspace</Link>
      </div>
    );
  }
  const type = agentType(world, selected);
  const agents = world.agents.filter((a) => a.typeKey === selected);
  return (
    <div className="space-y-3">
      <div><p className="text-sm font-semibold">{type?.name}</p><p className="text-xs text-fg-subtle">{type?.description}</p></div>
      <ul className="space-y-2">
        {agents.map((agent) => {
          const run = currentRun(world, agent.id);
          const task = byId(world.tasks, agent.taskId);
          return (
            <li key={agent.id} className="rounded-lg border border-line p-2.5">
              <div className="flex items-center gap-2">
                <Avatar name={agent.name} agent size="sm" />
                <span className="flex-1 text-[13px] font-medium">{agent.name}</span>
                <StatusPill size="sm" meta={AGENT_STATUS[agent.status]} />
              </div>
              {task && <p className="mt-1.5 text-xs text-fg-muted">{task.key} {task.title} · {byId(world.projects, task.projectId)?.name}</p>}
              {run && (
                <button type="button" onClick={() => onOpenRun(run.id)} className="mt-1.5 block w-full rounded-md px-1.5 py-1 text-left text-xs text-primary-strong hover:bg-surface-2">
                  Inspect "{run.title}" · {duration(executionSeconds(run, world.now))}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function LiveOperations() {
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<string>("developer");
  const [runFilter, setRunFilter] = useState<"active" | "all">("active");
  const runId = params.get("run");
  const openRun = (id: string) => setParams((p) => { p.set("run", id); return p; });
  const closeRun = () => setParams((p) => { p.delete("run"); return p; });

  const inFlight = world.executions.filter((e) => IN_FLIGHT.includes(e.status));
  const failed = world.executions.filter((e) => e.status === "failed");
  const q = queues(world);
  const load = bottlenecks(world);
  const maxLoad = Math.max(1, ...load.map((b) => b.load));
  const runs = (runFilter === "active" ? inFlight : world.executions).slice().sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  const running = world.sim.running;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Live Operations"
        crumbs={[{ label: "Company command" }]}
        description="Agent runs in flight, handoffs between agents, queues, human approval dependencies, failures and bottlenecks."
        meta={<span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-2xs text-fg-muted"><Dot tone={running ? "success" : "neutral"} pulse={running} />{running ? "Live" : "Paused"} · {formatDateTime(world.now)} (simulated)</span>}
      />

      <section aria-label="Operational figures" className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <Kpi label="Runs in flight" value={inFlight.filter((e) => e.status !== "paused").length} icon={Activity} hint={`${inFlight.filter((e) => e.status === "paused").length} paused`} />
        <Kpi label="Retrying" value={world.executions.filter((e) => e.status === "retrying" || e.attempt > 1).length} icon={RotateCcw} tone="cyan" hint="runs on a later attempt" />
        <Kpi label="Failed runs" value={failed.length} icon={CircleX} tone={failed.length ? "danger" : "success"} hint="each opens an incident" />
        <Kpi label="Ready to start" value={q.ready.length} icon={Layers} tone="primary" hint="dependencies done" />
        <Kpi label="Waiting on other work" value={q.waitingOnWork.length} icon={Hourglass} tone="neutral" hint="dependencies open" />
        <Kpi label="Waiting on people" value={q.waitingOnPeople.length} icon={Hand} tone="violet" hint="review or input needed" />
      </section>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Delivery workflow" subtitle="Agents in Phases 7 to 11, the approval gates between them, and the Project Owner Agent overseeing all of them. Select a stage or gate." icon={Waypoints}>
          <PipelineGraph world={world} selected={selected} onSelect={setSelected} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-fg-subtle">
            <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-primary" />Work flowing to a gate (animated while running)</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded border border-dashed border-violet" />Human approval gate</span>
            <span className="flex items-center gap-1.5"><span className="h-0 w-5 border-t border-dashed border-cyan" />Project Owner oversight</span>
          </div>
        </Panel>
        <Panel title="Details" subtitle="The selected stage or gate" icon={Activity}>
          <SelectionDetail world={world} selected={selected} onOpenRun={openRun} />
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel title="Agent runs" subtitle="Select a run to inspect its logs and controls" icon={Activity} flush
          actions={<Segmented label="Runs shown" value={runFilter} onChange={setRunFilter} options={[{ value: "active", label: `In flight (${inFlight.length})` }, { value: "all", label: `All (${world.executions.length})` }]} />}>
          <DataTable<Execution>
            rows={runs}
            rowKey={(e) => e.id}
            onRowClick={(e) => openRun(e.id)}
            selectedKey={runId ?? undefined}
            empty="No runs in flight"
            columns={[
              { key: "agent", header: "Agent", sortValue: (e) => byId(world.agents, e.agentId)?.name ?? "",
                render: (e) => { const a = byId(world.agents, e.agentId); return <span className="flex items-center gap-2"><Avatar name={a?.name ?? ""} agent size="sm" /><span className="whitespace-nowrap">{a?.name}</span></span>; } },
              { key: "title", header: "Activity", render: (e) => <div className="min-w-48"><div>{e.title}</div><div className="text-2xs text-fg-subtle">{byId(world.projects, e.projectId)?.name ?? "Company-wide"}</div></div> },
              { key: "duration", header: "Duration", align: "right", sortValue: (e) => executionSeconds(e, world.now), render: (e) => <span className="whitespace-nowrap">{duration(executionSeconds(e, world.now))}</span> },
              { key: "attempt", header: "Attempt", align: "right", hideBelow: "2xl", render: (e) => `${e.attempt} of ${e.maxAttempts}` },
              { key: "status", header: "Status", sortValue: (e) => e.status, render: (e) => <StatusPill meta={EXECUTION_STATUS[e.status]} /> },
            ]}
          />
        </Panel>

        <div className="space-y-5">
          <Panel title="Bottlenecks" subtitle="Waiting work, pending decisions and blocked work per MVP phase" icon={Clock}>
            <ul className="space-y-2.5">
              {load.map((b) => (
                <li key={b.phase}>
                  <div className="flex items-center justify-between text-xs"><span className="font-medium">Phase {b.phase}: {b.name}</span><span className="text-fg-subtle tabular">{b.waitingTasks} waiting · {b.pendingDecisions} decisions · {b.blocked} blocked</span></div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-3"><div className={b === load[0] && b.load > 0 ? "h-full rounded-full bg-warning" : "h-full rounded-full bg-primary"} style={{ width: `${(b.load / maxLoad) * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Human approval dependencies" subtitle="Work waiting for a person" icon={Hand} flush>
            {q.waitingOnPeople.length === 0 ? <EmptyState title="Nothing is waiting for people" /> : (
              <ul className="divide-y divide-line">
                {q.waitingOnPeople.map((t) => {
                  const decisions = decisionsFor(world, t);
                  return (
                    <li key={t.id} className="px-4 py-2.5">
                      <div className="flex items-center justify-between gap-2"><span className="text-[13px] font-medium">{t.key} {t.title}</span><StatusPill size="sm" meta={TASK_STATE[t.state]} /></div>
                      <div className="text-2xs text-fg-subtle">{byId(world.projects, t.projectId)?.name}</div>
                      <div className="mt-1 flex flex-wrap gap-1">{decisions.map((d) => <Link key={d.id} to={`/decisions?id=${d.id}`}><Tag tone="violet">{d.code}</Tag></Link>)}</div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Queues" subtitle="Ready to start, and waiting on other work" icon={Layers} flush>
          <ul className="divide-y divide-line">
            {[...q.ready.map((t) => ({ t, ready: true })), ...q.waitingOnWork.map((t) => ({ t, ready: false }))].map(({ t, ready }) => (
              <li key={t.id} className="flex items-center gap-2 px-4 py-2">
                <span className="min-w-0 flex-1"><span className="block truncate text-[13px]">{t.key} {t.title}</span><span className="block text-2xs text-fg-subtle">{byId(world.projects, t.projectId)?.name}{!ready ? ` · after ${t.dependsOn.map((d) => byId(world.tasks, d)?.key).join(", ")}` : ""}</span></span>
                {ready ? <Tag tone="cyan">Ready</Tag> : <Tag>Waiting</Tag>}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Failed runs and retries" subtitle="Failures open incidents; retries are limited and role-checked" icon={CircleX} flush>
          <ul className="divide-y divide-line">
            {world.executions.filter((e) => e.status === "failed" || e.attempt > 1).map((e) => (
              <li key={e.id}>
                <button type="button" onClick={() => openRun(e.id)} className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-surface-2">
                  <span className="min-w-0 flex-1"><span className="block truncate text-[13px]">{e.title}</span><span className="block truncate text-2xs text-fg-subtle">{e.output ?? "No output"} · attempt {e.attempt} of {e.maxAttempts}</span></span>
                  <StatusPill size="sm" meta={EXECUTION_STATUS[e.status]} />
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <ExecutionDrawer executionId={runId} onClose={closeRun} />
    </div>
  );
}
