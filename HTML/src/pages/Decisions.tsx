/* S07 Human Decision Center and its three views: the Approval Inbox, Recommendations and Escalations. Every decision
   opens the same review panel (?id=<decision id>), so a decision reached from a notification, the command palette,
   a project or a phase looks and behaves the same. */
import { useState, type ReactNode } from "react";
import {
  Ban, Bot, CircleCheck, Clock, FileCheck, Fingerprint, Hourglass, Inbox, Lightbulb, Scale, Search, ShieldExclamationPoint, ThumbsDown, UserRound, Users,
} from "lucide-react";
import { useSearchParams } from "react-router";
import { aRole, DecisionReview, KIND_META, rolesText } from "@/components/decisions/DecisionReview";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { DECISION_STATUS, PRIORITY } from "@/components/ui/status";
import { Tabs } from "@/components/ui/Tabs";
import { phaseDef } from "@/data/lifecycle";
import { formatDate, relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import { canDecide, humanChoice, inQueue, linkedRecords, QUEUES, recommendationStats, recommendedOption, sortDecisions, type DecisionQueue } from "@/store/decisions";
import { actorName, byId, isOpenDecision, isOverdue, latestVersion } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Decision, DecisionKind, World } from "@/types";

/** The review panel, driven by the address so any page can link to a decision. */
function useReview() {
  const [params, setParams] = useSearchParams();
  const set = (id: string | null) =>
    setParams((p) => {
      if (id) p.set("id", id);
      else p.delete("id");
      return p;
    });
  const id = params.get("id");
  return { id, open: (decisionId: string) => set(decisionId), drawer: <DecisionReview decisionId={id} onClose={() => set(null)} /> };
}

function Select<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as T)} aria-label={label} className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] sm:w-72">
      <Search className="size-4 text-fg-subtle" aria-hidden />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Search decisions" aria-label="Search decisions" className="min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-subtle" />
    </label>
  );
}

function matches(world: World, d: Decision, query: string): boolean {
  const q = query.toLowerCase().trim();
  if (!q) return true;
  return `${d.code} ${d.title} ${d.question} ${byId(world.projects, d.projectId)?.name ?? ""} ${actorName(world, d.originAgentId)}`.toLowerCase().includes(q);
}

function Deadline({ world, decision }: { world: World; decision: Decision }) {
  if (!isOpenDecision(decision)) return <span className="text-fg-subtle">Decided {decision.outcome ? formatDate(decision.outcome.at) : ""}</span>;
  const overdue = isOverdue(decision, world.now);
  return <span className={cn("inline-flex items-center gap-1", overdue ? "font-medium text-danger" : "text-fg-muted")}><Clock className="size-3" aria-hidden />{overdue ? `Overdue ${relative(decision.deadline, world.now).replace(" ago", "")}` : `Due ${relative(decision.deadline, world.now)}`}</span>;
}

/** One decision as a card: what is asked, what the agent recommends and why, the alternatives, risks, evidence,
    deadline and who decides. */
export function DecisionCard({ world, decision, onOpen, role }: { world: World; decision: Decision; onOpen: () => void; role: Parameters<typeof canDecide>[1] }) {
  const recommended = recommendedOption(decision);
  const alternatives = decision.options.filter((o) => o.key !== decision.recommended);
  const project = byId(world.projects, decision.projectId);
  const agentName = actorName(world, decision.originAgentId);
  const mine = isOpenDecision(decision) && canDecide(decision, role);
  return (
    <button type="button" onClick={onOpen} aria-label={`${decision.code} ${decision.title}`}
      className={cn("flex min-w-0 flex-col rounded-[var(--radius-panel)] border bg-surface p-4 text-left shadow-panel transition-colors hover:border-line-strong hover:bg-surface-2",
        isOverdue(decision, world.now) ? "border-danger/50" : "border-line")}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag>{decision.code}</Tag>
        <StatusPill size="sm" meta={KIND_META[decision.kind]} />
        <StatusPill size="sm" meta={PRIORITY[decision.priority]} />
        {decision.status !== "pending" && <StatusPill size="sm" meta={DECISION_STATUS[decision.status]} />}
      </div>
      <h3 className="mt-2 font-medium leading-snug text-fg">{decision.title}</h3>
      <p className="mt-0.5 text-2xs text-fg-subtle">{project?.name} · Phase {decision.phase}, {phaseDef(decision.phase).short}</p>

      <div className="mt-3 rounded-lg bg-surface-2 px-3 py-2">
        <p className="flex items-center gap-1.5 text-2xs text-fg-subtle"><Avatar name={agentName} agent size="sm" className="size-5" />{agentName} recommends</p>
        <p className="mt-1 text-[13px] font-medium">{recommended?.title ?? "No recommendation"}</p>
        <p className="mt-0.5 line-clamp-2 text-xs text-fg-muted">{decision.rationale}</p>
        {decision.outcome && (
          <p className="mt-1.5 flex items-start gap-1.5 border-t border-line pt-1.5 text-xs"><UserRound className="mt-px size-3.5 shrink-0 text-fg-subtle" aria-hidden /><span><span className="text-fg-muted">Decided: </span>{humanChoice(decision)} <span className="text-fg-subtle">({actorName(world, decision.outcome.by)})</span></span></p>
        )}
      </div>

      <dl className="mt-3 grid gap-1.5 text-xs">
        {alternatives.length > 0 && <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Alternatives:</dt><dd className="truncate">{alternatives.map((o) => o.title).join(" · ")}</dd></div>}
        {decision.risks.length > 0 && <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Risk:</dt><dd className="line-clamp-1">{decision.risks[0]}{decision.risks.length > 1 ? ` (+${decision.risks.length - 1} more)` : ""}</dd></div>}
        <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Evidence:</dt><dd className="truncate">{decision.evidence.map((e) => e.ref).join(", ")}</dd></div>
      </dl>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-2xs">
        <Deadline world={world} decision={decision} />
        <span className="flex flex-wrap items-center gap-1.5">
          {isOpenDecision(decision) && decision.blockedBy && <Tag tone="warning" icon={Ban}>Waiting for evidence</Tag>}
          {mine ? <Tag tone="violet" icon={UserRound}>You decide</Tag> : <span className="text-fg-subtle">Decides: {decision.allowedRoles.map((r) => ROLE_LABELS[r]).join(" or ")}</span>}
        </span>
      </div>
    </button>
  );
}

function CardGrid({ world, decisions, onOpen, empty }: { world: World; decisions: Decision[]; onOpen: (id: string) => void; empty: string }) {
  const role = useDemo((s) => s.role);
  if (decisions.length === 0) return <Panel><EmptyState icon={Scale} title={empty} hint="Change the filters, or start the simulation: agents raise new decisions as work moves on." /></Panel>;
  return (
    <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
      {decisions.map((d) => <DecisionCard key={d.id} world={world} decision={d} role={role} onOpen={() => onOpen(d.id)} />)}
    </div>
  );
}

const KIND_FILTER: [DecisionKind | "all", string][] = [["all", "All kinds"], ["approval", "Approvals"], ["recommendation", "Recommendations"], ["escalation", "Escalations"], ["question", "Questions"]];
const QUEUE_ICON: Record<DecisionQueue, typeof Scale> = { pending: Hourglass, high: ShieldExclamationPoint, overdue: Clock, approved: CircleCheck, rejected: ThumbsDown, deferred: Hourglass, all: Scale };
const QUEUE_TONE = { pending: "violet", high: "warning", overdue: "danger", approved: "success", rejected: "danger", deferred: "neutral", all: "primary" } as const;

export function DecisionCenter() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const review = useReview();
  const [queue, setQueue] = useState<DecisionQueue>("pending");
  const [kind, setKind] = useState<DecisionKind | "all">("all");
  const [project, setProject] = useState("all");
  const [mineOnly, setMineOnly] = useState(false);
  const [query, setQuery] = useState("");
  const shown = sortDecisions(world.decisions.filter((d) =>
    inQueue(world, d, queue) && (kind === "all" || d.kind === kind) && (project === "all" || d.projectId === project) && (!mineOnly || canDecide(d, role)) && matches(world, d, query)));
  const forMe = world.decisions.filter((d) => isOpenDecision(d) && canDecide(d, role)).length;

  return (
    <div className="space-y-5">
      <PageHeader title="Decision Center" crumbs={[{ label: "Human governance" }]}
        description="Agents recommend; people decide. Every recommendation, approval, escalation and question waiting for a person, with the evidence, the options and the full history."
        meta={<Tag tone="violet" icon={UserRound}>{forMe} for {aRole(role)}</Tag>}
        actions={<SearchBox value={query} onChange={setQuery} />} />

      <section aria-label="Decision queues" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {QUEUES.filter((q) => q.id !== "all").map((q) => (
          <Kpi key={q.id} label={q.label} value={world.decisions.filter((d) => inQueue(world, d, q.id)).length} icon={QUEUE_ICON[q.id]} tone={QUEUE_TONE[q.id]} hint={q.hint}
            onClick={() => setQueue(q.id)} pressed={queue === q.id} />
        ))}
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant={queue === "all" ? "primary" : "secondary"} aria-pressed={queue === "all"} onClick={() => setQueue("all")}>All decisions {world.decisions.length}</Button>
        <Select label="Kind" value={kind} onChange={setKind} options={KIND_FILTER} />
        <Select label="Project" value={project} onChange={setProject} options={[["all", "All projects"], ...world.projects.map((p) => [p.id, p.name] as [string, string])]} />
        <label className="inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px]">
          <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} className="accent-[var(--primary)]" />
          Only what {aRole(role)} can decide
        </label>
        <span className="ml-auto text-xs text-fg-subtle" aria-live="polite">{shown.length} shown · {QUEUES.find((q) => q.id === queue)!.label}</span>
      </div>

      <CardGrid world={world} decisions={shown} onOpen={review.open} empty="No decisions match" />
      {review.drawer}
    </div>
  );
}

export function ApprovalInbox() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const review = useReview();
  const approvals = world.decisions.filter((d) => d.kind === "approval");
  const open = sortDecisions(approvals.filter(isOpenDecision));
  const ready = open.filter((d) => canDecide(d, role) && !d.blockedBy);
  const waitingEvidence = open.filter((d) => canDecide(d, role) && d.blockedBy);
  const others = open.filter((d) => !canDecide(d, role));
  const decided = sortDecisions(approvals.filter((d) => !isOpenDecision(d)));

  const row = (d: Decision, extra?: ReactNode) => {
    const artifact = byId(world.artifacts, d.artifactId);
    return (
      <li key={d.id}>
        <button type="button" onClick={() => review.open(d.id)} className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left hover:bg-surface-2">
          <Tag>{d.code}</Tag>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-medium">{d.title}</span>
            <span className="block text-2xs text-fg-subtle">{byId(world.projects, d.projectId)?.name} · from {actorName(world, d.originAgentId)}{artifact && !d.blockedBy ? ` · ${artifact.title} v${latestVersion(artifact).no}` : ""}</span>
            {extra}
          </span>
          <span className="text-2xs"><Deadline world={world} decision={d} /></span>
          <StatusPill size="sm" meta={PRIORITY[d.priority]} />
        </button>
      </li>
    );
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Approval Inbox" crumbs={[{ label: "Human governance" }, { label: "Decision Center", to: "/decisions" }]}
        description={`Approvals for ${aRole(role)}: baselines, design changes, change sets, reviews and sign-offs. An approval binds to the exact version reviewed; a later version needs a new approval.`} />
      <section aria-label="Approval summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Ready for you" value={ready.length} icon={Inbox} tone="violet" hint="evidence in place" />
        <Kpi label="Waiting for evidence" value={waitingEvidence.length} icon={Ban} tone="warning" hint="e.g. sandbox tests still running" />
        <Kpi label="With other roles" value={others.length} icon={Users} tone="neutral" hint="you can add suggestions" />
        <Kpi label="Decided" value={decided.length} icon={CircleCheck} tone="success" hint="approved or sent back" />
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Ready for your decision" subtitle={`As ${ROLE_LABELS[role].toLowerCase()}`} icon={Inbox} flush>
          {ready.length ? <ul className="divide-y divide-line">{ready.map((d) => row(d))}</ul> : <EmptyState icon={Inbox} title={`Nothing is waiting for ${aRole(role)}`} hint="Switch role in the top bar to see what other people approve." />}
        </Panel>
        <Panel title="Waiting for evidence" subtitle="Cannot be approved until the evidence is in" icon={Ban} flush>
          {waitingEvidence.length ? <ul className="divide-y divide-line">{waitingEvidence.map((d) => row(d, <span className="mt-1 block text-2xs text-warning">{d.blockedBy}</span>))}</ul> : <EmptyState icon={CircleCheck} title="No approval is waiting for evidence" />}
        </Panel>
        <Panel title="With other roles" subtitle="Read them, add a suggestion" icon={Users} flush>
          {others.length ? <ul className="divide-y divide-line">{others.map((d) => row(d, <span className="mt-1 block text-2xs text-fg-subtle">Decides: {rolesText(d.allowedRoles)}</span>))}</ul> : <EmptyState icon={Users} title="No approvals with other roles" />}
        </Panel>
        <Panel title="Decided approvals" subtitle="With the version each approval is bound to" icon={Fingerprint} flush>
          {decided.length ? (
            <ul className="divide-y divide-line">{decided.map((d) => row(d, (
              <span className="mt-1 flex flex-wrap items-center gap-1.5 text-2xs text-fg-subtle">
                <StatusPill size="sm" meta={DECISION_STATUS[d.status]} />
                {d.outcome && `${actorName(world, d.outcome.by)}, ${formatDate(d.outcome.at)}`}
                {d.outcome?.boundTo && <span className="font-mono">v{d.outcome.boundTo.version} · {d.outcome.boundTo.sha256.slice(0, 12)}…</span>}
              </span>
            )))}</ul>
          ) : <EmptyState icon={FileCheck} title="No approval has been decided yet" hint="Approve a change set or a sign-off and it appears here with the version it is bound to." />}
        </Panel>
      </div>
      {review.drawer}
    </div>
  );
}

export function Recommendations() {
  const world = useDemo((s) => s.world);
  const review = useReview();
  const [kind, setKind] = useState("all");
  const all = world.decisions.filter((d) => d.kind !== "approval");
  const rows = sortDecisions(all.filter((d) => kind === "all" || d.kind === kind));
  const stats = recommendationStats(all);
  return (
    <div className="space-y-5">
      <PageHeader title="Recommendations" crumbs={[{ label: "Human governance" }, { label: "Decision Center", to: "/decisions" }]}
        description="What each agent recommended and what people decided, side by side. People may accept, choose another option, enter their own, reject or defer; the recommendation is never edited." />
      <section aria-label="How people answered" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi label="Open" value={stats.open} icon={Hourglass} tone="violet" hint="waiting for a person" />
        <Kpi label="Accepted as recommended" value={stats.asRecommended} icon={CircleCheck} tone="success" />
        <Kpi label="Changed by people" value={stats.changed} icon={UserRound} tone="cyan" hint="another option or their own" />
        <Kpi label="Rejected or deferred" value={stats.rejected + stats.deferred} icon={ThumbsDown} tone="neutral" hint={`${stats.rejected} rejected, ${stats.deferred} deferred`} />
        <Kpi label="Agreement" value={stats.agreement === null ? "n/a" : `${stats.agreement}%`} icon={Bot} tone="primary" hint="kept as recommended" />
      </section>
      <Tabs value={kind} onValueChange={setKind}
        items={[{ value: "all", label: "All", count: all.length }, ...(["recommendation", "question", "escalation"] as const).map((k) => ({ value: k, label: KIND_META[k].label + "s", count: all.filter((d) => d.kind === k).length }))]}>
        <div className="pt-4">
          <Panel title={`${rows.length} recommendations`} icon={Lightbulb} flush>
            <DataTable<Decision>
              rows={rows}
              rowKey={(d) => d.id}
              onRowClick={(d) => review.open(d.id)}
              selectedKey={review.id ?? undefined}
              empty="No recommendations"
              columns={[
                { key: "code", header: "Code", sortValue: (d) => d.code, render: (d) => <Tag>{d.code}</Tag> },
                { key: "title", header: "Decision", render: (d) => <div className="min-w-52"><div className="font-medium">{d.title}</div><div className="text-2xs text-fg-subtle">{byId(world.projects, d.projectId)?.name} · Phase {d.phase}</div></div> },
                { key: "agent", header: "Agent", hideBelow: "xl", sortValue: (d) => actorName(world, d.originAgentId), render: (d) => <span className="flex items-center gap-1.5 whitespace-nowrap"><Avatar name={actorName(world, d.originAgentId)} agent size="sm" />{actorName(world, d.originAgentId)}</span> },
                { key: "recommended", header: "Agent recommended", render: (d) => <span className="flex items-start gap-1.5"><Bot className="mt-0.5 size-3.5 shrink-0 text-primary-strong" aria-hidden />{recommendedOption(d)?.title}</span> },
                { key: "decided", header: "People decided", render: (d) => d.outcome ? <span className="flex items-start gap-1.5"><UserRound className="mt-0.5 size-3.5 shrink-0 text-fg-subtle" aria-hidden />{humanChoice(d)}</span> : <span className="text-fg-subtle">{d.status === "clarification_requested" ? "Question with the agent" : "Not yet"}</span> },
                { key: "status", header: "Status", sortValue: (d) => d.status, render: (d) => <StatusPill size="sm" meta={DECISION_STATUS[d.status]} /> },
                { key: "when", header: "Deadline", hideBelow: "lg", sortValue: (d) => d.deadline, render: (d) => <span className="text-xs whitespace-nowrap"><Deadline world={world} decision={d} /></span> },
              ]}
            />
          </Panel>
        </div>
      </Tabs>
      {review.drawer}
    </div>
  );
}

export function Escalations() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const review = useReview();
  const escalations = world.decisions.filter((d) => d.kind === "escalation");
  const open = sortDecisions(escalations.filter(isOpenDecision));
  const closed = sortDecisions(escalations.filter((d) => !isOpenDecision(d)));
  return (
    <div className="space-y-5">
      <PageHeader title="Escalations" crumbs={[{ label: "Human governance" }, { label: "Decision Center", to: "/decisions" }]}
        description="Problems an agent or the Project Owner Agent could not resolve within its authority: what is at stake, how long it has waited and who must decide." />
      <section aria-label="Escalation summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Open" value={open.length} icon={ShieldExclamationPoint} tone="danger" />
        <Kpi label="Overdue" value={open.filter((d) => isOverdue(d, world.now)).length} icon={Clock} tone="danger" hint="past their deadline" />
        <Kpi label="For you" value={open.filter((d) => canDecide(d, role)).length} icon={UserRound} tone="violet" hint={`as ${ROLE_LABELS[role].toLowerCase()}`} />
        <Kpi label="Resolved" value={closed.length} icon={CircleCheck} tone="success" />
      </section>

      <Panel title="How an escalation reaches a person" icon={ShieldExclamationPoint}>
        <ol className="grid gap-3 text-[13px] sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["1", "An agent detects it", "A failed run, a critical defect, a missed deadline or a risk above its threshold."],
            ["2", "The Project Owner Agent checks it", "It gathers the facts, the options and a recommendation; it cannot decide."],
            ["3", "The right role decides", "Only the roles named on the escalation may decide; the deadline is tracked."],
            ["4", "The workflow follows the decision", "Dates, risks and work change through the workflow engine, with the audit trail."],
          ].map(([n, title, text]) => (
            <li key={n} className="flex gap-3 rounded-lg bg-surface-2 p-3">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-danger-soft text-xs font-semibold text-danger">{n}</span>
              <span><span className="block font-medium">{title}</span><span className="text-xs text-fg-muted">{text}</span></span>
            </li>
          ))}
        </ol>
      </Panel>

      {open.length === 0 ? <Panel><EmptyState icon={CircleCheck} title="No open escalations" hint="Every escalation has been decided." /></Panel> : (
        <div className="grid gap-4 xl:grid-cols-2">
          {open.map((d) => {
            const links = linkedRecords(world, d);
            return (
              <article key={d.id} aria-label={`${d.code} ${d.title}`} className={cn("flex flex-col rounded-[var(--radius-panel)] border bg-surface p-4 shadow-panel", isOverdue(d, world.now) ? "border-danger/50" : "border-line")}>
                <div className="flex flex-wrap items-center gap-1.5"><Tag>{d.code}</Tag><StatusPill size="sm" meta={PRIORITY[d.priority]} />{d.status !== "pending" && <StatusPill size="sm" meta={DECISION_STATUS[d.status]} />}</div>
                <h3 className="mt-2 font-medium">{d.title}</h3>
                <p className="mt-1 text-[13px] text-fg-muted">{d.question}</p>
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
                  <div><dt className="text-fg-subtle">Raised by</dt><dd>{actorName(world, d.originAgentId)}</dd></div>
                  <div><dt className="text-fg-subtle">Waiting</dt><dd>{relative(d.createdAt, world.now).replace(" ago", "")}</dd></div>
                  <div><dt className="text-fg-subtle">Deadline</dt><dd><Deadline world={world} decision={d} /></dd></div>
                  <div><dt className="text-fg-subtle">Decides</dt><dd>{d.allowedRoles.map((r) => ROLE_LABELS[r]).join(" or ")}</dd></div>
                </dl>
                <div className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-xs">
                  <p className="text-fg-subtle">At stake</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">{d.risks.map((r) => <li key={r}>{r}</li>)}</ul>
                </div>
                {(links.risks.length > 0 || links.incidents.length > 0) && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {links.risks.map((r) => <Tag key={r.id} tone={r.status === "closed" ? "success" : "warning"}>{r.code} {r.status}</Tag>)}
                    {links.incidents.map((i) => <Tag key={i.id} tone={i.status === "closed" || i.status === "resolved" ? "success" : "danger"}>{i.code} {i.status}</Tag>)}
                  </div>
                )}
                <div className="mt-4 flex items-center justify-between gap-2 border-t border-line pt-3">
                  <span className="text-xs text-fg-muted">Recommends: <span className="font-medium text-fg">{recommendedOption(d)?.title}</span></span>
                  <Button size="sm" variant={canDecide(d, role) ? "primary" : "secondary"} onClick={() => review.open(d.id)}>{canDecide(d, role) ? "Review and decide" : "Review"}</Button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Panel title="Resolved escalations" icon={CircleCheck} flush>
        {closed.length === 0 ? <EmptyState icon={Hourglass} title="None resolved yet" hint="Decide an escalation and it moves here with the outcome." /> : (
          <ul className="divide-y divide-line">{closed.map((d) => (
            <li key={d.id}><button type="button" onClick={() => review.open(d.id)} className="flex w-full flex-wrap items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2">
              <Tag>{d.code}</Tag><span className="min-w-0 flex-1 text-[13px]">{d.title}<span className="block text-2xs text-fg-subtle">{humanChoice(d)}{d.outcome ? ` · ${actorName(world, d.outcome.by)}, ${formatDate(d.outcome.at)}` : ""}</span></span>
              <StatusPill size="sm" meta={DECISION_STATUS[d.status]} />
            </button></li>
          ))}</ul>
        )}
      </Panel>
      {review.drawer}
    </div>
  );
}
