/* The decision review panel (S07): the agent's recommendation and the human decision side by side, the options,
   the evidence, and every action a person may take. The rules are the store's (store/actions.ts decide): only the
   listed roles decide, nothing is approved before its evidence is in, an approval binds to the exact version, and
   the agent's recommendation is never edited. Opened from anywhere with ?id=<decision id>. */
import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowRight, Bot, CircleCheck, Clock, FileCheck, Fingerprint, Hourglass, Lightbulb, MessageCircleQuestion, MessageSquarePlus, PencilLine,
  RotateCcw, ScrollText, ShieldExclamationPoint, ThumbsDown, UserRound,
} from "lucide-react";
import { Link } from "react-router";
import { phasePath } from "@/app/navigation";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Drawer } from "@/components/ui/Overlays";
import { Field } from "@/components/ui/Panel";
import { ARTIFACT_STATUS, DECISION_STATUS, INCIDENT_STATUS, PRIORITY, RISK_STATUS, type StatusMeta } from "@/components/ui/status";
import { phaseDef } from "@/data/lifecycle";
import { formatDateTime, relative } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { canDecide, decisionAudit, decisionEffects, humanChoice, linkedRecords, recommendedOption } from "@/store/decisions";
import { actorName, byId, isOpenDecision, isOverdue, latestVersion } from "@/store/selectors";
import { ROLE_PEOPLE, useDemo } from "@/store/useDemo";
import type { DecisionEvent, DecisionKind, Role } from "@/types";

export const KIND_META: Record<DecisionKind, StatusMeta> = {
  approval: { label: "Approval", tone: "violet", icon: FileCheck },
  recommendation: { label: "Recommendation", tone: "primary", icon: Lightbulb },
  escalation: { label: "Escalation", tone: "danger", icon: ShieldExclamationPoint },
  question: { label: "Question", tone: "cyan", icon: MessageCircleQuestion },
};

const EVENT_LABEL: Record<DecisionEvent["action"], string> = {
  raised: "Raised", answered: "Answered", accept: "Accepted", choose_option: "Chose an option", custom: "Own option", reject: "Rejected",
  defer: "Deferred", clarify: "Asked a question", comment: "Suggestion", reopen: "Reopened",
};

const OTHER = "__other__";

export function rolesText(roles: Role[]): string {
  return roles.map((r) => ROLE_LABELS[r].toLowerCase()).join(" or ");
}

/** "an owner", "a reviewer", "an owner or project manager". */
export function aRole(roles: Role | Role[]): string {
  const text = rolesText(Array.isArray(roles) ? roles : [roles]);
  return `${/^[aeiou]/.test(text) ? "an" : "a"} ${text}`;
}

function Section({ title, icon: Icon, children, className }: { title: string; icon?: typeof Bot; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-fg-muted uppercase">{Icon && <Icon className="size-3.5" aria-hidden />}{title}</h3>
      {children}
    </section>
  );
}

function Notice({ tone, children }: { tone: "warning" | "danger" | "info" | "success"; children: ReactNode }) {
  const styles = { warning: "border-warning/30 bg-warning-soft text-warning", danger: "border-danger/30 bg-danger-soft text-danger", info: "border-primary/30 bg-primary-soft text-fg", success: "border-success/30 bg-success-soft text-success" }[tone];
  return <div className={cn("rounded-lg border px-3 py-2 text-[13px]", styles)}>{children}</div>;
}

export function DecisionReview({ decisionId, onClose }: { decisionId: string | null; onClose: () => void }) {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const setRole = useDemo((s) => s.setRole);
  const data = useDataService();
  const action = useRuleAction();
  const decision = byId(world.decisions, decisionId ?? undefined);
  const [choice, setChoice] = useState<string>("");
  const [custom, setCustom] = useState("");
  const [comment, setComment] = useState("");
  const [constraints, setConstraints] = useState("");

  useEffect(() => {
    action.clear();
    setChoice(decision?.outcome?.optionKey ?? decision?.recommended ?? "");
    setCustom("");
    setComment("");
    setConstraints("");
  }, [decisionId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!decision) return <Drawer open={false} onOpenChange={() => onClose()} title="Decision">{null}</Drawer>;

  const open = isOpenDecision(decision);
  const allowed = canDecide(decision, role);
  const approval = decision.kind === "approval";
  const recommended = recommendedOption(decision);
  const project = byId(world.projects, decision.projectId);
  const agent = byId(world.agents, decision.originAgentId);
  const artifact = byId(world.artifacts, decision.artifactId);
  const links = linkedRecords(world, decision);
  const effects = decisionEffects(world, decision);
  const trail = decisionAudit(world, decision);

  const run = (input: Parameters<typeof data.decide>[0], success: string, after?: () => void) =>
    action.run(() => {
      data.decide(input);
      after?.();
    }, success);
  const base = { decisionId: decision.id, comment, constraints };
  const record = () => {
    if (choice === OTHER) return run({ ...base, action: "custom", custom }, "Recorded your own option. The recommendation is kept unchanged beside it.");
    if (!choice) return action.run(() => { throw new Error("Choose an option first"); });
    if (choice === decision.recommended) return run({ ...base, action: "accept" }, approval ? "Approved." : "Accepted the recommendation.");
    return run({ ...base, action: "choose_option", optionKey: choice }, approval ? "Sent back to the agent with your comments." : "Recorded your choice. The original recommendation is kept beside it.");
  };
  const selectedIsRecommended = choice === decision.recommended;

  return (
    <Drawer
      open
      onOpenChange={(isOpen) => !isOpen && onClose()}
      title={<span className="flex flex-wrap items-center gap-2"><Tag>{decision.code}</Tag>{decision.title}</span>}
      description={
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <StatusPill size="sm" meta={DECISION_STATUS[decision.status]} />
          <StatusPill size="sm" meta={KIND_META[decision.kind]} />
          <StatusPill size="sm" meta={PRIORITY[decision.priority]} />
          {isOverdue(decision, world.now) && <Tag tone="danger" icon={Clock}>Overdue</Tag>}
        </span>
      }
      width="w-[min(820px,100vw)]"
      footer={
        <div className="flex w-full flex-col gap-2">
          <span className="text-2xs text-fg-subtle">Acting as {ROLE_LABELS[role].toLowerCase()} ({actorName(world, ROLE_PEOPLE[role])}). Simulated; recorded in this demo only.</span>
          {open ? (
            <div className="flex flex-wrap justify-end gap-2">
              <Button size="sm" icon={MessageSquarePlus} onClick={() => run({ ...base, action: "comment" }, "Suggestion added to the history.", () => setComment(""))}>Add suggestion</Button>
              <Button size="sm" icon={MessageCircleQuestion} onClick={() => run({ ...base, action: "clarify" }, "Question sent. The agent answers while the simulation runs.", () => setComment(""))}>Ask the agent</Button>
              <Button size="sm" icon={Hourglass} onClick={() => run({ ...base, action: "defer" }, "Deferred. It can be reopened.")}>Defer</Button>
              <Button size="sm" variant="danger" icon={approval ? RotateCcw : ThumbsDown} onClick={() => run({ ...base, action: "reject" }, approval ? "Sent back to the agent with your comments." : "Rejected. The recommendation is kept in the record.")}>
                {approval ? "Send back" : "Reject"}
              </Button>
              {!approval && !selectedIsRecommended && (
                <Button size="sm" icon={PencilLine} onClick={record}>{choice === OTHER ? "Use my own option" : "Use the selected option"}</Button>
              )}
              <Button size="sm" variant="primary" icon={CircleCheck} onClick={() => run({ ...base, action: "accept" }, approval ? "Approved." : "Accepted the recommendation.")}>
                {approval ? "Approve" : "Accept recommendation"}
              </Button>
            </div>
          ) : decision.status === "deferred" ? (
            <div className="flex justify-end"><Button size="sm" icon={RotateCcw} onClick={() => run({ ...base, action: "reopen" }, "Reopened. It is waiting for a decision again.")}>Reopen</Button></div>
          ) : null}
        </div>
      }
    >
      <div className="space-y-6">
        {action.error && <Notice tone="danger"><span role="alert">{action.error}</span></Notice>}
        {action.done && <Notice tone="success"><span role="status">{action.done}</span></Notice>}

        {open && !allowed && (
          <Notice tone="info">
            <p>Only {aRole(decision.allowedRoles)} may decide {decision.code}. You are acting as {ROLE_LABELS[role].toLowerCase()}, so you can add a suggestion but not decide.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {decision.allowedRoles.map((r) => <Button key={r} size="sm" icon={UserRound} onClick={() => { setRole(r); action.clear(); }}>Act as {ROLE_LABELS[r].toLowerCase()}</Button>)}
            </div>
          </Notice>
        )}
        {open && decision.blockedBy && <Notice tone="warning">Cannot be decided yet: {decision.blockedBy}. You can still ask a question, add a suggestion or defer it.</Notice>}
        {decision.status === "clarification_requested" && <Notice tone="warning">Waiting for {agent?.name ?? "the agent"} to answer a question. Start the simulation and it answers within a minute of simulated time.</Notice>}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <Field label="Project">{project ? <Link to={`/projects/${project.id}?tab=decisions`} className="hover:text-primary-strong">{project.name}</Link> : decision.projectId}</Field>
          <Field label="Phase"><Link to={`${phasePath(decision.phase)}?project=${decision.projectId}`} className="hover:text-primary-strong">Phase {decision.phase}, {phaseDef(decision.phase).short}</Link></Field>
          <Field label="Raised by"><Link to={`/agents?agent=${decision.originAgentId}`} className="inline-flex items-center gap-1.5 hover:text-primary-strong">{agent && <Avatar name={agent.name} agent size="sm" />}{actorName(world, decision.originAgentId)}</Link></Field>
          <Field label="Raised">{formatDateTime(decision.createdAt)}</Field>
          <Field label="Deadline"><span className={cn(isOverdue(decision, world.now) && "text-danger")}>{formatDateTime(decision.deadline)} ({relative(decision.deadline, world.now)})</span></Field>
          <Field label="Who decides">{decision.allowedRoles.map((r) => ROLE_LABELS[r]).join(" or ")}</Field>
        </dl>

        <p className="rounded-lg bg-surface-2 px-3 py-2.5 text-sm">{decision.question}</p>

        <div className="grid gap-3 md:grid-cols-2">
          <section aria-label="Original AI recommendation" className="rounded-lg border border-primary/30 bg-primary-soft/30 p-3">
            <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-primary-strong uppercase"><Bot className="size-3.5" aria-hidden />Original AI recommendation</h3>
            <p className="mt-2 font-medium">{recommended?.title ?? "No recommendation"}</p>
            {recommended && <p className="mt-0.5 text-[13px] text-fg-muted">{recommended.description}</p>}
            <p className="mt-2 text-[13px]">{decision.rationale}</p>
            <p className="mt-2 text-2xs text-fg-subtle">As raised by {actorName(world, decision.originAgentId)}. Kept exactly as raised, whatever people decide.</p>
          </section>
          <section aria-label="Final human decision" className={cn("rounded-lg border p-3", decision.outcome ? "border-success/30 bg-success-soft/30" : "border-dashed border-line-strong")}>
            <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-fg-muted uppercase"><UserRound className="size-3.5" aria-hidden />Final human decision</h3>
            {decision.outcome ? (
              <>
                <p className="mt-2 flex flex-wrap items-center gap-2 font-medium">{humanChoice(decision)} <StatusPill size="sm" meta={DECISION_STATUS[decision.status]} /></p>
                {decision.outcome.comment && <p className="mt-1.5 text-[13px]">"{decision.outcome.comment}"</p>}
                {decision.outcome.constraints && <p className="mt-1.5 text-[13px]"><span className="text-fg-muted">Constraints: </span>{decision.outcome.constraints}</p>}
                <p className="mt-2 text-2xs text-fg-subtle">By {actorName(world, decision.outcome.by)}, {formatDateTime(decision.outcome.at)}</p>
                {decision.outcome.boundTo && (
                  <p className="mt-1.5 flex items-start gap-1.5 text-2xs text-fg-subtle"><Fingerprint className="mt-px size-3 shrink-0" aria-hidden />Bound to {artifact?.title ?? decision.outcome.boundTo.artifactId} v{decision.outcome.boundTo.version}, sha256 <span className="font-mono">{decision.outcome.boundTo.sha256.slice(0, 16)}…</span></p>
                )}
              </>
            ) : (
              <p className="mt-2 text-[13px] text-fg-muted">{decision.status === "clarification_requested" ? "Not decided: a question is with the agent." : "Not decided yet."}</p>
            )}
          </section>
        </div>

        {open && (
          <Section title={approval ? "Outcomes: approve, or send back with comments" : "Options: accept the recommendation, choose another or enter your own"} icon={PencilLine}>
            <fieldset className="space-y-2">
              <legend className="sr-only">Options for {decision.code}</legend>
              {decision.options.map((option) => (
                <label key={option.key} className={cn("flex gap-3 rounded-lg border p-3 transition-colors", approval ? "border-line" : choice === option.key ? "cursor-pointer border-primary bg-primary-soft/40" : "cursor-pointer border-line hover:bg-surface-2")}>
                  {!approval && <input type="radio" name={`option-${decision.id}`} value={option.key} checked={choice === option.key} onChange={() => setChoice(option.key)} className="mt-1 accent-[var(--primary)]" />}
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2 font-medium">{option.title}{option.key === decision.recommended && <Tag tone="primary" icon={Bot}>Recommended</Tag>}</span>
                    <span className="mt-0.5 block text-[13px] text-fg-muted">{option.description}</span>
                    {(option.pros.length > 0 || option.cons.length > 0) && (
                      <span className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                        <span>{option.pros.map((p) => <span key={p} className="block text-success">+ {p}</span>)}</span>
                        <span>{option.cons.map((c) => <span key={c} className="block text-warning">− {c}</span>)}</span>
                      </span>
                    )}
                  </span>
                </label>
              ))}
              {!approval && (
                <label className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", choice === OTHER ? "border-primary bg-primary-soft/40" : "border-line hover:bg-surface-2")}>
                  <input type="radio" name={`option-${decision.id}`} value={OTHER} checked={choice === OTHER} onChange={() => setChoice(OTHER)} className="mt-1 accent-[var(--primary)]" />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">Other: my own option</span>
                    {choice === OTHER && (
                      <textarea value={custom} onChange={(e) => setCustom(e.target.value)} rows={2} aria-label="Your own option" placeholder="Describe the technology or approach you want instead"
                        className="mt-2 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-primary" />
                    )}
                  </span>
                </label>
              )}
            </fieldset>
            <div className="mt-3 grid gap-3 sm:grid-cols-[3fr_2fr]">
              <label className="block text-xs font-medium text-fg-muted">
                Comments, suggestion or question
                <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} placeholder="Needed to reject, send back, ask or suggest; optional otherwise"
                  className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] font-normal text-fg outline-none focus:border-primary" />
              </label>
              <label className="block text-xs font-medium text-fg-muted">
                Constraints (optional)
                <textarea value={constraints} onChange={(e) => setConstraints(e.target.value)} rows={3} placeholder="e.g. Purchase orders above AED 50,000 stay on premises"
                  className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] font-normal text-fg outline-none focus:border-primary" />
              </label>
            </div>
            {approval && artifact && (
              <p className="mt-2 flex items-start gap-1.5 text-2xs text-fg-subtle">
                <Fingerprint className="mt-px size-3 shrink-0" aria-hidden />
                Approving binds to {artifact.title} v{latestVersion(artifact).no} (sha256 <span className="font-mono">{latestVersion(artifact).sha256.slice(0, 16)}…</span>). A later version needs a new approval.
              </p>
            )}
          </Section>
        )}

        <div className="grid gap-5 md:grid-cols-2">
          <Section title="Risks and trade-offs" icon={ShieldExclamationPoint}>
            {decision.risks.length ? <ul className="list-disc space-y-1 pl-4 text-[13px]">{decision.risks.map((r) => <li key={r}>{r}</li>)}</ul> : <p className="text-[13px] text-fg-muted">None recorded.</p>}
          </Section>
          <Section title="Supporting evidence" icon={ScrollText}>
            <ul className="space-y-1.5 text-[13px]">
              {decision.evidence.map((e) => <li key={e.ref + e.label} className="flex items-start gap-2"><Tag className="mt-px">{e.ref}</Tag><span>{e.label}</span></li>)}
            </ul>
            <LinkedRecords links={links} />
          </Section>
        </div>

        {effects.length > 0 && (
          <Section title="What this decision changed" icon={ArrowRight}>
            <ul className="space-y-1.5 text-[13px]">{effects.map((e) => <li key={e.id} className="flex gap-2"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-success" aria-hidden />{e.text}</li>)}</ul>
            {project && <p className="mt-2 text-xs"><Link to={`/projects/${project.id}`} className="text-primary-strong hover:underline">See {project.name}</Link></p>}
          </Section>
        )}

        <Section title="Decision history" icon={Clock}>
          <ol className="relative space-y-3 border-l border-line pl-4">
            {decision.history.map((event, i) => {
              const isAgent = !byId(world.people, event.actor) && event.actor !== "system";
              return (
                <li key={`${event.at}-${i}`} className="relative">
                  <span className="absolute top-1 -left-[21px] size-2.5 rounded-full border-2 border-surface bg-line-strong" aria-hidden />
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Avatar name={actorName(world, event.actor)} agent={isAgent} size="sm" />
                    <span className="font-medium text-fg">{actorName(world, event.actor)}</span>
                    <Tag tone={isAgent ? "primary" : "neutral"}>{EVENT_LABEL[event.action]}</Tag>
                    <span className="text-fg-subtle">{formatDateTime(event.at)}</span>
                  </div>
                  <p className="mt-1 text-[13px] text-fg-muted">{event.summary}</p>
                </li>
              );
            })}
          </ol>
        </Section>

        <Section title="Approval audit trail" icon={Fingerprint}>
          {trail.length === 0 ? <p className="text-[13px] text-fg-muted">No audit entries yet.</p> : (
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full text-xs">
                <thead><tr className="border-b border-line text-left text-2xs tracking-wide text-fg-subtle uppercase"><th className="px-3 py-2">When</th><th className="px-3 py-2">Actor</th><th className="px-3 py-2">Action</th><th className="px-3 py-2">Detail</th></tr></thead>
                <tbody>{trail.map((a) => (
                  <tr key={a.id} className="border-b border-line last:border-0 align-top">
                    <td className="px-3 py-2 whitespace-nowrap text-fg-muted">{formatDateTime(a.at)}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{actorName(world, a.actor)}</td>
                    <td className="px-3 py-2 font-mono text-2xs">{a.action}</td>
                    <td className="px-3 py-2 text-fg-muted">{a.detail}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-2xs text-fg-subtle">In Agentra the audit trail is append-only and recorded server-side; agents can raise and answer, never approve.</p>
        </Section>
      </div>
    </Drawer>
  );
}

function LinkedRecords({ links }: { links: ReturnType<typeof linkedRecords> }) {
  const rows = [
    ...links.risks.map((r) => ({ key: r.id, code: r.code, title: r.title, meta: RISK_STATUS[r.status], to: "/risk" })),
    ...links.incidents.map((i) => ({ key: i.id, code: i.code, title: i.title, meta: INCIDENT_STATUS[i.status], to: "/risk" })),
    ...links.artifacts.map((a) => ({ key: a.id, code: `v${latestVersion(a).no}`, title: a.title, meta: ARTIFACT_STATUS[latestVersion(a).status], to: `/projects/${a.projectId}?tab=documents` })),
  ];
  if (rows.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-2xs font-medium tracking-wide text-fg-subtle uppercase">Linked records, as they are now</p>
      <ul className="space-y-1.5">
        {rows.map((r) => (
          <li key={r.key}><Link to={r.to} className="flex items-center gap-2 rounded-md border border-line px-2 py-1.5 text-xs hover:bg-surface-2"><Tag>{r.code}</Tag><span className="min-w-0 flex-1 truncate">{r.title}</span><StatusPill size="sm" meta={r.meta} /></Link></li>
        ))}
      </ul>
    </div>
  );
}
