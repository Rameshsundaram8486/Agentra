/* The root-cause analysis workspace (S09). For each failure: what happened, the recorded evidence, the probable cause,
   business impact, containment, corrective action, who is responsible, how it will be verified and where it stands.
   Recorded facts and the AI's hypothesis are always shown apart; a hypothesis becomes a confirmed cause only when a
   person confirms it, and only a person verifies and closes an incident. */
import type { ReactNode } from "react";
import { BrainCircuit, CircleCheck, Database, ExternalLink, Microscope, ShieldCheck, Wrench } from "lucide-react";
import { Link } from "react-router";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Field } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { INCIDENT_STATUS, PRIORITY } from "@/components/ui/status";
import { formatDateTime, relative } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS, type IncidentCommand } from "@/store/actions";
import { actorName, byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Incident, World } from "@/types";

const STEPS: Incident["status"][] = ["open", "investigating", "resolved", "closed"];

function Block({ title, icon: Icon, tone, children, label }: { title: string; icon: typeof Database; tone: "fact" | "ai" | "plain"; children: ReactNode; label?: ReactNode }) {
  return (
    <section aria-label={title} className={cn("rounded-lg border p-3", tone === "fact" ? "border-line bg-surface-2/60" : tone === "ai" ? "border-dashed border-violet/50 bg-violet-soft/25" : "border-line")}>
      <h4 className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold tracking-wide text-fg-muted uppercase">
        <span className="flex items-center gap-1.5"><Icon className="size-3.5" aria-hidden />{title}</span>
        {label}
      </h4>
      <div className="mt-2 text-[13px]">{children}</div>
    </section>
  );
}

export function RcaDetail({ world, incident }: { world: World; incident: Incident }) {
  const role = useDemo((s) => s.role);
  const data = useDataService();
  const action = useRuleAction();
  const { rca } = incident;
  const agent = byId(world.agents, incident.agentId);
  const run = byId(world.executions, incident.executionId);
  const project = byId(world.projects, incident.projectId);
  const decision = world.decisions.find((d) => d.evidence.some((e) => e.ref === incident.code));
  const command = (c: IncidentCommand, done: string) => action.run(() => data.updateIncident(incident.id, c), done);
  const step = STEPS.indexOf(incident.status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5"><Tag>{incident.code}</Tag><StatusPill size="sm" meta={PRIORITY[incident.severity]} /><StatusPill size="sm" meta={INCIDENT_STATUS[incident.status]} /></div>
          <h3 className="mt-1.5 text-base font-semibold">{incident.title}</h3>
          <p className="text-xs text-fg-subtle">{project?.name} · {formatDateTime(incident.occurredAt)} ({relative(incident.occurredAt, world.now)})</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {incident.status === "open" && <Button size="sm" icon={Microscope} onClick={() => command("investigate", "Investigation started.")}>Start investigating</Button>}
          {incident.status !== "closed" && !rca.causeConfirmedBy && <Button size="sm" icon={CircleCheck} onClick={() => command("confirm_cause", "Probable cause confirmed and recorded as yours.")}>Confirm the cause</Button>}
          {incident.status === "investigating" && <Button size="sm" icon={Wrench} onClick={() => command("resolve", "Marked resolved. Verify it before closing.")}>Mark resolved</Button>}
          {incident.status === "resolved" && <Button size="sm" variant="primary" icon={ShieldCheck} onClick={() => command("close", "Verified and closed.")}>Verify and close</Button>}
        </div>
      </div>

      <ol aria-label="Resolution status" className="grid grid-cols-4 gap-1.5 text-center text-2xs">
        {STEPS.map((s, i) => (
          <li key={s} className={cn("rounded-md px-2 py-1.5 font-medium", i < step ? "bg-success-soft text-success" : i === step ? "bg-primary-soft text-primary-strong ring-1 ring-primary/40" : "bg-surface-2 text-fg-subtle")} aria-current={i === step ? "step" : undefined}>
            {INCIDENT_STATUS[s].label}
          </li>
        ))}
      </ol>

      {action.error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger">{action.error}</p>}
      {action.done && <p role="status" className="rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-success">{action.done}</p>}

      <Block title="What happened" icon={Database} tone="fact" label={<Tag icon={Database}>From records</Tag>}>{rca.whatHappened}</Block>

      <div className="grid gap-3 lg:grid-cols-2">
        <Block title="Observed evidence" icon={Database} tone="fact" label={<Tag icon={Database}>Confirmed facts</Tag>}>
          <ul className="list-disc space-y-1 pl-4">{rca.facts.map((f) => <li key={f}>{f}</li>)}</ul>
        </Block>
        <Block title="Probable cause" icon={BrainCircuit} tone={rca.causeConfirmedBy ? "fact" : "ai"}
          label={rca.causeConfirmedBy ? <Tag tone="success" icon={CircleCheck}>Confirmed by {actorName(world, rca.causeConfirmedBy)}</Tag> : <Tag tone="violet" icon={BrainCircuit}>AI hypothesis, {rca.confidence} confidence</Tag>}>
          <p>{rca.hypothesis}</p>
          {!rca.causeConfirmedBy && <p className="mt-2 text-2xs text-fg-subtle">Not a fact until a person confirms it against the evidence.</p>}
          {rca.causeConfirmedAt && <p className="mt-2 text-2xs text-fg-subtle">Confirmed {formatDateTime(rca.causeConfirmedAt)}</p>}
        </Block>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Block title="Business impact" icon={ExternalLink} tone="plain">{rca.businessImpact}</Block>
        <Block title="Containment" icon={ShieldCheck} tone="plain" label={<Tag tone="violet">Recommended</Tag>}>{rca.containment}</Block>
        <Block title="Corrective action" icon={Wrench} tone="plain" label={<Tag tone="violet">Recommended</Tag>}>{rca.correctiveAction}</Block>
      </div>

      <dl className="grid gap-3 rounded-lg border border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Responsible person"><span className="inline-flex items-center gap-1.5"><Avatar name={actorName(world, rca.ownerId)} size="sm" />{actorName(world, rca.ownerId)}</span></Field>
        <Field label="Agent involved">{agent ? <Link to={`/agents?agent=${agent.id}`} className="inline-flex items-center gap-1.5 hover:text-primary-strong"><Avatar name={agent.name} agent size="sm" />{agent.name}</Link> : "None"}</Field>
        <Field label="Failed run">{run ? <Link to={`/agents/history?run=${run.id}`} className="hover:text-primary-strong">{run.title}</Link> : "None"}</Field>
        <Field label="Escalated as">{decision ? <Link to={`/decisions?id=${decision.id}`} className="hover:text-primary-strong">{decision.code}</Link> : "Not escalated"}</Field>
      </dl>

      <Block title="Verification criteria" icon={ShieldCheck} tone="plain" label={rca.verifiedBy ? <Tag tone="success" icon={CircleCheck}>Verified by {actorName(world, rca.verifiedBy)}</Tag> : <Tag>Not verified yet</Tag>}>
        {rca.verification}
        {rca.resolvedBy && <p className="mt-2 text-2xs text-fg-subtle">Resolved by {actorName(world, rca.resolvedBy)}{rca.verifiedBy ? "" : "; someone else must verify and close it"}.</p>}
      </Block>
      <p className="text-2xs text-fg-subtle">Acting as {ROLE_LABELS[role].toLowerCase()}. Owners and project managers investigate and resolve; owners and reviewers verify and close, never the person who resolved it. Agents propose causes and actions and never close incidents.</p>
    </div>
  );
}

export function RcaList({ world, selectedId, onSelect }: { world: World; selectedId?: string; onSelect: (id: string) => void }) {
  if (world.incidents.length === 0) return <EmptyState title="No incidents" />;
  return (
    <ul className="space-y-1.5" aria-label="Incidents">
      {world.incidents.map((i) => (
        <li key={i.id}>
          <button type="button" onClick={() => onSelect(i.id)} aria-pressed={i.id === selectedId}
            className={cn("w-full rounded-lg border p-2.5 text-left transition-colors", i.id === selectedId ? "border-primary bg-primary-soft/40" : "border-line hover:bg-surface-2")}>
            <span className="flex flex-wrap items-center gap-1.5"><Tag>{i.code}</Tag><StatusPill size="sm" meta={INCIDENT_STATUS[i.status]} /></span>
            <span className="mt-1 block text-[13px] font-medium">{i.title}</span>
            <span className="block text-2xs text-fg-subtle">{byId(world.projects, i.projectId)?.code} · {relative(i.occurredAt, world.now)} · {i.rca.causeConfirmedBy ? "cause confirmed" : "hypothesis"}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
