/* One agent run: what it is doing, for which project and task, its inputs, output, cost and logs, with simulated
   pause, resume and retry that follow the real permission rule (owners and project managers only). */
import { useEffect, useRef } from "react";
import { ArrowRight, CirclePause, CirclePlay, RotateCcw, ShieldCheck, Terminal } from "lucide-react";
import { Link } from "react-router";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Drawer } from "@/components/ui/Overlays";
import { Field } from "@/components/ui/Panel";
import { EXECUTION_STATUS, TASK_STATE } from "@/components/ui/status";
import { duration, formatDateTime, formatTime, number, usd } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { executionSeconds } from "@/store/operations";
import { agentType, byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import { useRuleAction } from "./useRuleAction";

export function LogConsole({ lines, live, className }: { lines: { at: string; level: "info" | "warn" | "error"; text: string; source?: string }[]; live?: boolean; className?: string }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" });
  }, [lines.length]);
  return (
    <div className={cn("max-h-72 overflow-y-auto rounded-lg border border-line bg-[#070b17] p-3 font-mono text-[12px] leading-5 text-slate-300", className)} role="log" aria-live={live ? "polite" : "off"}>
      {lines.map((line, i) => (
        <div key={`${line.at}-${i}`} className="flex gap-2">
          <span className="shrink-0 text-slate-500">{formatTime(line.at)}</span>
          {line.source && <span className="shrink-0 text-cyan-300/80">{line.source}</span>}
          <span className={cn(line.level === "error" ? "text-red-400" : line.level === "warn" ? "text-amber-300" : "text-slate-200")}>{line.text}</span>
        </div>
      ))}
      {live && <div className="mt-1 text-slate-500"><span className="live-pulse">▍</span></div>}
      <div ref={end} />
    </div>
  );
}

export function ExecutionDrawer({ executionId, onClose }: { executionId: string | null; onClose: () => void }) {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const data = useDataService();
  const action = useRuleAction();
  const execution = byId(world.executions, executionId ?? undefined);
  const agent = execution ? byId(world.agents, execution.agentId) : undefined;
  const project = execution ? byId(world.projects, execution.projectId) : undefined;
  const task = execution ? byId(world.tasks, execution.taskId) : undefined;
  const next = execution?.handoffTo ? agentType(world, execution.handoffTo) : undefined;
  useEffect(() => action.clear(), [executionId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!execution || !agent) return <Drawer open={false} onOpenChange={() => onClose()} title="Run">{null}</Drawer>;
  const inFlight = execution.status === "running" || execution.status === "retrying";
  const control = (command: "pause" | "resume" | "retry", label: string) => action.run(() => data.controlExecution(execution.id, command), label);

  return (
    <Drawer
      open
      onOpenChange={(open) => !open && onClose()}
      title={execution.title}
      description={<span className="inline-flex flex-wrap items-center gap-2"><StatusPill meta={EXECUTION_STATUS[execution.status]} /> Run {execution.id} · attempt {execution.attempt} of {execution.maxAttempts}</span>}
      width="w-[min(620px,100vw)]"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="text-2xs text-fg-subtle">Simulated controls. Acting as {ROLE_LABELS[role].toLowerCase()}.</span>
          <div className="flex gap-2">
            {execution.status === "running" && <Button size="sm" icon={CirclePause} onClick={() => control("pause", "Paused (simulated). The agent stops after its current step.")}>Pause</Button>}
            {execution.status === "paused" && <Button size="sm" icon={CirclePlay} onClick={() => control("resume", "Resumed (simulated).")}>Resume</Button>}
            {execution.status === "failed" && <Button size="sm" variant="primary" icon={RotateCcw} onClick={() => control("retry", "Retry started (simulated).")}>Retry</Button>}
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {action.error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger">{action.error}</p>}
        {action.done && <p role="status" className="rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-success">{action.done}</p>}

        <Link to={`/agents?agent=${agent.id}`} className="flex items-center gap-3 rounded-lg border border-line p-3 hover:bg-surface-2">
          <Avatar name={agent.name} agent size="lg" />
          <span className="min-w-0 flex-1">
            <span className="block font-medium">{agent.name}</span>
            <span className="block text-xs text-fg-subtle">{agentType(world, agent.typeKey)?.description}</span>
          </span>
          <ArrowRight className="size-4 text-fg-subtle" aria-hidden />
        </Link>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <Field label="Project">{project ? <Link to={`/projects/${project.id}`} className="hover:text-primary-strong">{project.name}</Link> : "Company-wide"}</Field>
          <Field label="Task">{task ? <span className="inline-flex flex-wrap items-center gap-1.5">{task.key} <StatusPill size="sm" meta={TASK_STATE[task.state]} /></span> : "None"}</Field>
          <Field label="Duration"><span className="tabular">{duration(executionSeconds(execution, world.now))}</span>{inFlight && <span className="ml-1 text-2xs text-fg-subtle">so far</span>}</Field>
          <Field label="Started">{formatDateTime(execution.startedAt)}</Field>
          <Field label="Model">{agentType(world, agent.typeKey)?.model} · effort {agentType(world, agent.typeKey)?.effort}</Field>
          <Field label="Tokens and cost"><span className="tabular">{number(execution.tokensIn)} in · {number(execution.tokensOut)} out · {usd(execution.costUsd)}</span></Field>
        </dl>

        <div>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Input</h3>
          <p className="rounded-lg bg-surface-2 px-3 py-2 text-[13px]">{execution.input}</p>
        </div>
        <div>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Output</h3>
          <p className="rounded-lg bg-surface-2 px-3 py-2 text-[13px]">{execution.output ?? (inFlight ? "Not finished yet." : "No output recorded.")}</p>
          {next && <p className="mt-1.5 flex items-center gap-1.5 text-xs text-fg-muted">Hands over to <Tag tone="cyan">{next.name}</Tag></p>}
        </div>
        <div>
          <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><Terminal className="size-3.5" aria-hidden />Execution log</h3>
          <LogConsole lines={execution.logs} live={inFlight} />
        </div>
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-2xs text-fg-subtle">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          In Agentra, an agent's output is saved only after it passes the guardrails in code (schema, grounding, forbidden claims, secrets), and it is never approved by an agent.
        </p>
      </div>
    </Drawer>
  );
}
