/* Command Center panels: what needs a person, live activity, project health and the agent workforce. */
import { ArrowRight, CircleAlert } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Avatar } from "@/components/ui/Avatar";
import { Dot, StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Tooltip } from "@/components/ui/Overlays";
import { Progress } from "@/components/ui/States";
import { AGENT_STATUS, HEALTH, PRIORITY, TONE_DOT, TONE_TEXT, type Tone } from "@/components/ui/status";
import { phaseDef } from "@/data/lifecycle";
import { formatDate, relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import {
  agentStatusCounts, agentType, byId, completion, currentPhase, isOverdue, nextMilestone, openDecisions, projectAgents, projectHealth,
} from "@/store/selectors";
import type { ActivityEvent, Agent, Project, Role, World } from "@/types";

/* Human attention ---------------------------------------------------------------------------------- */

export function AttentionList({ world, role, limit = 6 }: { world: World; role: Role; limit?: number }) {
  const decisions = openDecisions(world).sort((a, b) => Number(isOverdue(b, world.now)) - Number(isOverdue(a, world.now)));
  if (decisions.length === 0) return <p className="px-4 py-6 text-center text-[13px] text-fg-muted">Nothing is waiting for a person.</p>;
  return (
    <>
      <ul className="divide-y divide-line">
        {decisions.slice(0, limit).map((d) => {
          const overdue = isOverdue(d, world.now);
          const mine = d.allowedRoles.includes(role);
          return (
            <li key={d.id}>
              <Link to={`/decisions?id=${d.id}`} className="flex gap-3 px-4 py-2.5 hover:bg-surface-2">
                <StatusPill size="sm" meta={PRIORITY[d.priority]} className="mt-0.5" />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-fg">{d.title}</span>
                  <span className="block text-2xs text-fg-subtle">
                    {d.code} · {byId(world.projects, d.projectId)?.name} · needs {d.allowedRoles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ")}
                  </span>
                  {d.blockedBy && <span className="mt-0.5 block text-2xs text-warning">Waiting: {d.blockedBy}</span>}
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <span className={cn("text-2xs tabular", overdue ? "font-semibold text-danger" : "text-fg-subtle")}>{overdue ? `overdue ${relative(d.deadline, world.now).replace(" ago", "")}` : `due ${relative(d.deadline, world.now)}`}</span>
                  {mine && <Tag tone="violet">You can decide</Tag>}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <Link to="/decisions" className="flex items-center justify-center gap-1 border-t border-line py-2 text-xs text-primary-strong hover:bg-surface-2">
        All {decisions.length} decisions <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </>
  );
}

/* Activity ------------------------------------------------------------------------------------------ */

const SEVERITY_TONE: Record<ActivityEvent["severity"], Tone> = { info: "primary", success: "success", warning: "warning", critical: "danger" };

export function ActivityFeed({ world, limit = 10 }: { world: World; limit?: number }) {
  return (
    <ol aria-live="polite" aria-label="Activity, newest first" className="divide-y divide-line">
      {world.activity.slice(0, limit).map((event, index) => {
        const agent = byId(world.agents, event.agentId);
        const project = byId(world.projects, event.projectId);
        return (
          <li key={event.id} className={cn("flex gap-2.5 px-4 py-2.5", index === 0 && world.sim.running && "bg-primary-soft/30")}>
            {agent ? <Avatar name={agent.name} agent size="sm" className="mt-0.5" /> : <span className="grid size-6 shrink-0 place-items-center"><Dot tone={SEVERITY_TONE[event.severity]} /></span>}
            <div className="min-w-0 flex-1">
              <p className={cn("text-[13px]", event.severity === "critical" ? "text-fg" : "text-fg")}>
                {event.severity === "critical" && <CircleAlert className="mr-1 inline size-3.5 align-[-2px] text-danger" aria-label="Critical" />}
                {event.text}
              </p>
              <p className="text-2xs text-fg-subtle">
                {relative(event.at, world.now)}
                {project && <> · <Link to={`/projects/${project.id}`} className="hover:text-fg">{project.name}</Link></>}
              </p>
            </div>
            <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", TONE_DOT[SEVERITY_TONE[event.severity]])} aria-hidden />
          </li>
        );
      })}
    </ol>
  );
}

/* Projects ------------------------------------------------------------------------------------------ */

function AgentStack({ agents }: { agents: Agent[] }) {
  const shown = agents.slice(0, 3);
  return (
    <Tooltip content={agents.map((a) => a.name).join(", ") || "No agents"}>
      <span className="inline-flex items-center" tabIndex={0}>
        {shown.map((a, i) => <Avatar key={a.id} name={a.name} agent size="sm" className={cn("ring-2 ring-surface", i > 0 && "-ml-1.5")} />)}
        {agents.length > 3 && <span className="-ml-1.5 grid size-6 place-items-center rounded-lg bg-surface-3 text-2xs font-semibold ring-2 ring-surface">+{agents.length - 3}</span>}
      </span>
    </Tooltip>
  );
}

export function ProjectHealthTable({ world }: { world: World }) {
  const navigate = useNavigate();
  const rows = world.projects.filter((p) => p.status !== "completed");
  return (
    <DataTable<Project>
      rows={rows}
      rowKey={(p) => p.id}
      onRowClick={(p) => navigate(`/projects/${p.id}`)}
      columns={[
        { key: "name", header: "Project", sortValue: (p) => p.name,
          render: (p) => <div className="min-w-44"><div className="font-medium">{p.name}</div><div className="text-2xs text-fg-subtle">{byId(world.customers, p.customerId)?.name}</div></div> },
        { key: "phase", header: "Phase", sortValue: (p) => currentPhase(p).phase,
          render: (p) => <span className="whitespace-nowrap text-fg-muted">{currentPhase(p).phase}. {phaseDef(currentPhase(p).phase).short}{!phaseDef(currentPhase(p).phase).mvp && <Tag className="ml-1.5">Preview</Tag>}</span> },
        { key: "complete", header: "Complete", sortValue: completion,
          render: (p) => <div className="flex w-28 items-center gap-2"><Progress value={completion(p)} tone={HEALTH[projectHealth(world, p).health].tone === "danger" ? "danger" : "primary"} label={`${p.name}: ${completion(p)}% complete`} /><span className="text-xs tabular">{completion(p)}%</span></div> },
        { key: "health", header: "Health", sortValue: (p) => ["critical", "at_risk", "on_track", "on_hold"].indexOf(projectHealth(world, p).health),
          render: (p) => {
            const h = projectHealth(world, p);
            return <Tooltip content={<ul className="space-y-0.5">{h.reasons.slice(0, 4).map((r) => <li key={r}>{r}</li>)}</ul>}><span tabIndex={0}><StatusPill meta={HEALTH[h.health]} /></span></Tooltip>;
          } },
        { key: "agents", header: "Agents", hideBelow: "2xl", render: (p) => <AgentStack agents={projectAgents(world, p.id)} /> },
        { key: "milestone", header: "Next milestone", hideBelow: "2xl",
          render: (p) => { const m = nextMilestone(p); return m ? <div><div className="text-xs">{m.title}</div><div className={cn("text-2xs", Date.parse(m.due) < Date.parse(world.now) ? "text-danger" : "text-fg-subtle")}>{formatDate(m.due)}</div></div> : <span className="text-xs text-fg-subtle">None</span>; } },
        { key: "decisions", header: "Decisions", align: "right", sortValue: (p) => openDecisions(world, p.id).length,
          render: (p) => { const n = openDecisions(world, p.id).length; return <span className={n ? "font-semibold text-violet" : "text-fg-subtle"}>{n}</span>; } },
      ]}
    />
  );
}

/* Workforce ----------------------------------------------------------------------------------------- */

const ORDER: Agent["status"][] = ["working", "waiting_approval", "blocked", "failed", "completed", "idle"];

export function Workforce({ world }: { world: World }) {
  const counts = agentStatusCounts(world);
  const total = world.agents.length;
  const busy = world.agents.filter((a) => a.status !== "idle").sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-3" role="img" aria-label={ORDER.map((s) => `${counts[s]} ${AGENT_STATUS[s].label.toLowerCase()}`).join(", ")}>
        {ORDER.map((s) => counts[s] > 0 && <span key={s} className={TONE_DOT[AGENT_STATUS[s].tone]} style={{ width: `${(counts[s] / total) * 100}%` }} />)}
      </div>
      <ul className="mt-2.5 grid grid-cols-3 gap-x-3 gap-y-1">
        {ORDER.map((s) => (
          <li key={s} className="flex items-center gap-1.5 text-2xs text-fg-muted">
            <span className={cn("size-2 rounded-sm", TONE_DOT[AGENT_STATUS[s].tone])} aria-hidden />
            <span className="truncate">{AGENT_STATUS[s].label}</span>
            <span className={cn("ml-auto font-semibold tabular", TONE_TEXT[AGENT_STATUS[s].tone])}>{counts[s]}</span>
          </li>
        ))}
      </ul>
      <ul className="mt-3 divide-y divide-line border-t border-line">
        {busy.slice(0, 7).map((agent) => {
          const task = byId(world.tasks, agent.taskId);
          const run = world.executions.find((e) => e.agentId === agent.id && (e.status === "running" || e.status === "retrying"));
          return (
            <li key={agent.id}>
              <Link to={`/agents?agent=${agent.id}`} className="flex items-center gap-2.5 py-2 hover:bg-surface-2">
                <Avatar name={agent.name} agent size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px]">{agent.name}</span>
                  <span className="block truncate text-2xs text-fg-subtle">{run?.title ?? (task ? `${task.key} ${task.title}` : agentType(world, agent.typeKey)?.description)}</span>
                </span>
                <StatusPill size="sm" meta={AGENT_STATUS[agent.status]} />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
