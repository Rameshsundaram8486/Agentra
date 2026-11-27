/* An agent's profile: role, current work, model, permissions, autonomy, statistics, run history and its live
   console. Opened from the Agent Control Center, the directory and search (?agent=<id>). */
import { Activity, KeyRound, Lock, Workflow } from "lucide-react";
import { Link } from "react-router";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Overlays";
import { Field } from "@/components/ui/Panel";
import { AGENT_STATUS, EXECUTION_STATUS } from "@/components/ui/status";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { PHASES } from "@/data/lifecycle";
import { duration, number, relative } from "@/lib/format";
import { currentRun, executionSeconds, runsOf, successRate } from "@/store/operations";
import { agentType, byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import { LogConsole } from "./ExecutionDrawer";

export const AUTONOMY_TEXT = {
  supervised: "Supervised: every output is reviewed by a person before it counts.",
  controlled: "Controlled: acts within its tools and budgets; consequential steps need a person.",
  conditional: "Conditional: acts on its own in agreed conditions; exceptions go to a person.",
} as const;

export function AgentProfile({ agentId, onClose, onOpenRun }: { agentId: string | null; onClose: () => void; onOpenRun: (id: string) => void }) {
  const world = useDemo((s) => s.world);
  const agent = byId(world.agents, agentId ?? undefined);
  if (!agent) return <Drawer open={false} onOpenChange={() => onClose()} title="Agent">{null}</Drawer>;
  const type = agentType(world, agent.typeKey)!;
  const run = currentRun(world, agent.id);
  const task = byId(world.tasks, agent.taskId);
  const project = byId(world.projects, agent.projectId);
  const history = runsOf(world, agent.id);
  return (
    <Drawer open onOpenChange={(open) => !open && onClose()} title={agent.name} description={`${CATEGORY_LABELS[type.category]} · ${type.inMvp ? "MVP" : "Preview, not in the MVP"}`} width="w-[min(620px,100vw)]">
      <div className="space-y-5">
        <div className="flex items-start gap-3">
          <Avatar name={agent.name} agent size="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-[13px]">{type.description}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <StatusPill meta={AGENT_STATUS[agent.status]} />
              <Tag>{`since ${relative(agent.since, world.now)}`}</Tag>
              <Tag tone="violet">{type.autonomy}</Tag>
            </div>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <Field label="Assigned project">{project ? <Link className="hover:text-primary-strong" to={`/projects/${project.id}`}>{project.name}</Link> : "None"}</Field>
          <Field label="Current task">{task ? `${task.key} ${task.title}` : "None"}</Field>
          <Field label="Model">{type.model}<span className="block text-2xs text-fg-subtle">effort {type.effort}, through the model gateway</span></Field>
          <Field label="Runs"><span className="tabular">{number(agent.runs)}</span></Field>
          <Field label="Success rate"><span className="tabular">{successRate(agent)}%</span><span className="block text-2xs text-fg-subtle">{agent.failed} failed</span></Field>
          <Field label="Average run time"><span className="tabular">{duration(agent.avgSeconds)}</span></Field>
          <Field label="Phases">{type.phases.length ? type.phases.map((n) => PHASES[n - 1]!.short).join(", ") : "All (company-wide)"}</Field>
        </dl>

        {run && (
          <button type="button" onClick={() => onOpenRun(run.id)} className="block w-full rounded-lg border border-primary/30 bg-primary-soft/40 p-3 text-left hover:bg-primary-soft">
            <span className="flex items-center justify-between gap-2"><span className="text-[13px] font-medium">{run.title}</span><StatusPill size="sm" meta={EXECUTION_STATUS[run.status]} /></span>
            <span className="block text-2xs text-fg-subtle">{duration(executionSeconds(run, world.now))} so far · open the run to pause or inspect it</span>
          </button>
        )}

        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><KeyRound className="size-3.5" aria-hidden />Tool permissions</h3>
          <ul className="flex flex-wrap gap-1.5">{type.tools.map((t) => <li key={t}><Tag>{t}</Tag></li>)}</ul>
          <p className="mt-2 flex items-start gap-1.5 text-2xs text-fg-subtle"><Lock className="mt-0.5 size-3 shrink-0" aria-hidden />{AUTONOMY_TEXT[type.autonomy]} Agents never approve or record decisions.</p>
        </section>

        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><Activity className="size-3.5" aria-hidden />Activity console</h3>
          {run ? <LogConsole lines={run.logs} live={run.status === "running"} /> : <p className="text-[13px] text-fg-muted">Not running anything right now.</p>}
        </section>

        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><Workflow className="size-3.5" aria-hidden />Execution history</h3>
          {history.length === 0 ? <p className="text-[13px] text-fg-muted">No runs recorded in the demo data.</p> : (
            <ul className="divide-y divide-line rounded-lg border border-line">
              {history.map((e) => (
                <li key={e.id}>
                  <button type="button" onClick={() => onOpenRun(e.id)} className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-2">
                    <span className="min-w-0 flex-1"><span className="block truncate text-[13px]">{e.title}</span><span className="block text-2xs text-fg-subtle">{relative(e.startedAt, world.now)} · {duration(executionSeconds(e, world.now))}</span></span>
                    <StatusPill size="sm" meta={EXECUTION_STATUS[e.status]} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Drawer>
  );
}
