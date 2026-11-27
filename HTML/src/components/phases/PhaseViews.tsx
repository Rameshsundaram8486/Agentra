/* What each MVP phase shows for a project: requirements (7), architecture (8), development (9), QA (10) and UAT (11),
   plus preview content for the phases outside the MVP and a summary for phases a project has finished or not reached.
   Live statuses (decisions answered, builds passed, defects fixed, sign-off) are derived from the shared records. */
import type { ReactNode } from "react";
import { CircleCheck, CircleX, Link2, ShieldCheck } from "lucide-react";
import { Link } from "react-router";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Panel } from "@/components/ui/Panel";
import { EmptyState, Progress } from "@/components/ui/States";
import { ARTIFACT_STATUS, DECISION_STATUS, PHASE_STATE, TASK_STATE, TONE_SOFT, type Tone } from "@/components/ui/status";
import { ARCHITECTURE, DEVELOPMENT, PREVIEW, QA, REQUIREMENTS, UAT, type ReqKind, type RequirementItem } from "@/data/seed/phaseContent";
import { phaseDef } from "@/data/lifecycle";
import { formatDate } from "@/lib/format";
import { byId, latestVersion } from "@/store/selectors";
import type { Project, Task, World } from "@/types";

const KIND_LABEL: Record<ReqKind, string> = {
  objective: "Business objectives", functional: "Functional requirements", non_functional: "Non-functional requirements", business_rule: "Business rules",
  assumption: "Assumptions", dependency: "Dependencies", open_question: "Open questions",
};
const REQ_TONE = { confirmed: "success", proposed: "primary", open: "warning" } as const;

function decided(world: World, code: string): boolean {
  const d = world.decisions.find((x) => x.code === code);
  return d?.status === "approved" || d?.status === "modified";
}

/** A requirement whose open point was a decision becomes confirmed once that decision is made. */
function reqStatus(world: World, item: RequirementItem): RequirementItem["status"] {
  const code = item.source.match(/DEC-\d{3}/)?.[0];
  return code && decided(world, code) ? "confirmed" : item.status;
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: ReactNode; tone?: Tone }) {
  return (
    <div className={cn("rounded-lg px-3 py-2", TONE_SOFT[tone])}>
      <div className="text-lg leading-6 font-semibold tabular">{value}</div>
      <div className="text-2xs opacity-80">{label}</div>
    </div>
  );
}

function DocLink({ world, id }: { world: World; id: string }) {
  const doc = byId(world.artifacts, id);
  if (!doc) return null;
  const v = latestVersion(doc);
  return <Link to={`/knowledge?doc=${doc.id}`} className="inline-flex items-center gap-1.5 text-xs hover:text-primary-strong">{doc.title} v{v.no} <StatusPill size="sm" meta={ARTIFACT_STATUS[v.status]} /></Link>;
}

/* Phase 7 ------------------------------------------------------------------------------------------- */

export function RequirementsView({ world, projectId }: { world: World; projectId: string }) {
  const content = REQUIREMENTS[projectId];
  if (!content) return null;
  const items = content.items.map((i) => ({ ...i, status: reqStatus(world, i) }));
  const kinds = [...new Set(items.map((i) => i.kind))];
  const traced = items.filter((i) => i.design?.length || i.workItems?.length);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Items" value={items.length} />
        <Stat label="Confirmed" value={items.filter((i) => i.status === "confirmed").length} tone="success" />
        <Stat label="Proposed" value={items.filter((i) => i.status === "proposed").length} tone="primary" />
        <Stat label="Open" value={items.filter((i) => i.status === "open").length} tone="warning" />
      </div>
      <p className="text-xs text-fg-muted">Baseline: <DocLink world={world} id={content.baselineDoc} />. IDs and statuses are set by Agentra: confirmed only for a fact backed by a source or an answered decision.</p>
      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          {kinds.map((kind) => (
            <section key={kind}>
              <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">{KIND_LABEL[kind]}</h3>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {items.filter((i) => i.kind === kind).map((i) => (
                  <li key={i.id} className="flex items-start gap-3 px-3 py-2">
                    <Tag className="mt-0.5 shrink-0">{i.id}</Tag>
                    <span className="min-w-0 flex-1 text-[13px]">{i.title}<span className="block text-2xs text-fg-subtle">Source: {i.source}{i.priority ? ` · ${i.priority}` : ""}</span></span>
                    <Tag tone={REQ_TONE[i.status]}>{i.status}</Tag>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <div className="space-y-4">
          <section>
            <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Stakeholders</h3>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {content.stakeholders.map((s) => <li key={s.name} className="px-3 py-2 text-[13px]">{s.name} <Tag className="ml-1">{s.role}</Tag><span className="block text-2xs text-fg-subtle">{s.interest}</span></li>)}
            </ul>
          </section>
          <section>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><Link2 className="size-3.5" aria-hidden />Traceability</h3>
            {traced.length === 0 ? <p className="text-[13px] text-fg-muted">Design items and work items are linked once Phase 8 plans them.</p> : (
              <ul className="space-y-1.5">
                {traced.map((i) => (
                  <li key={i.id} className="rounded-lg border border-line px-3 py-2 text-2xs">
                    <span className="font-semibold">{i.id}</span> → {i.design?.join(", ") || "-"} → {i.workItems?.join(", ") || "-"} → {i.tests?.join(", ") || "no test yet"}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

/* Phase 8 ------------------------------------------------------------------------------------------- */

export function ArchitectureView({ world, projectId }: { world: World; projectId: string }) {
  const c = ARCHITECTURE[projectId];
  if (!c) return null;
  return (
    <div className="space-y-5">
      <p className="text-xs text-fg-muted">Design: <DocLink world={world} id={c.designDoc} /> · Security review: <DocLink world={world} id="doc-p-sec" /></p>
      <div className="grid gap-5 xl:grid-cols-[3fr_2fr]">
        <section>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Solution architecture</h3>
          <div className="space-y-2 rounded-lg border border-line p-3">
            {c.layers.map((layer) => (
              <div key={layer.name} className="grid grid-cols-[96px_1fr] items-center gap-3">
                <span className="text-2xs font-semibold tracking-wide text-fg-subtle uppercase">{layer.name}</span>
                <div className="flex flex-wrap gap-2">
                  {layer.items.map((item) => (
                    <span key={item.id} className="rounded-lg border border-primary/30 bg-primary-soft/50 px-2.5 py-1.5 text-xs"><span className="font-semibold text-primary-strong">{item.id}</span> {item.title}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <h3 className="mt-4 mb-1.5 text-xs font-semibold text-fg-muted">Integration design</h3>
          <ul className="space-y-1 text-xs">{c.integrations.map((i) => <li key={`${i.from}-${i.to}`} className="rounded-md bg-surface-2 px-2.5 py-1.5"><b>{i.from}</b> → <b>{i.to}</b> <span className="text-fg-subtle">via {i.how}</span></li>)}</ul>
        </section>
        <div className="space-y-4">
          <section>
            <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Technology options compared</h3>
            <ul className="space-y-1.5">
              {c.options.map((o) => (
                <li key={o.key} className="flex items-center gap-2 text-[13px]">
                  <span className="w-44 shrink-0 truncate">{o.title}</span>
                  <Progress value={(o.score / 5) * 100} tone={o.chosen ? "success" : "neutral"} label={`${o.title}: ${o.score} of 5`} />
                  <span className="w-8 text-right text-xs tabular">{o.score}</span>
                  {o.chosen && <Tag tone="success">chosen</Tag>}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-2xs text-fg-subtle">The agent scores; Agentra totals; people choose.</p>
          </section>
          <section>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted"><ShieldCheck className="size-3.5" aria-hidden />Security design (checklist)</h3>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {c.security.map((s) => (
                <li key={s.id} className="flex items-center gap-2 px-3 py-1.5 text-xs">
                  {s.verdict === "met" ? <CircleCheck className="size-3.5 text-success" aria-label="Met" /> : <CircleX className="size-3.5 text-warning" aria-label="Gap" />}
                  <span className="font-semibold">{s.id}</span><span className="flex-1">{s.title}</span>{s.severity && <Tag tone={s.severity === "high" ? "danger" : "warning"}>{s.severity}</Tag>}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Technical decisions</h3>
            <ul className="space-y-1">
              {c.decisions.map((d) => {
                const status = d.id === "ADR-002" && decided(world, "DEC-003") ? "accepted" : d.status;
                return <li key={d.id} className="flex items-center gap-2 text-xs"><Tag>{d.id}</Tag><span className="flex-1">{d.title}</span><Tag tone={status === "accepted" ? "success" : "violet"}>{status}</Tag></li>;
              })}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}

/* Phase 9 ------------------------------------------------------------------------------------------- */

type Build = { label: string; tone: Tone };

/** Build status of a work item's latest change set, from its task and its approval decision. */
export function buildStatus(world: World, task: Task): Build {
  if (task.state === "completed") return { label: "Passed, merged", tone: "success" };
  if (task.state === "failed") return { label: "Failed", tone: "danger" };
  if (task.state === "waiting_for_review") {
    const approval = world.decisions.find((d) => d.kind === "approval" && d.title.includes(task.key) && d.projectId === task.projectId);
    return approval?.blockedBy ? { label: "Building and testing", tone: "primary" } : { label: "Passed", tone: "success" };
  }
  if (task.state === "in_progress") return { label: "Not built yet", tone: "neutral" };
  return { label: "-", tone: "neutral" };
}

function reviewStatus(task: Task): Build {
  if (task.state === "completed") return { label: "Approved", tone: "success" };
  if (task.state === "waiting_for_review") return { label: "In review", tone: "violet" };
  if (task.state === "changes_requested") return { label: "Changes requested", tone: "warning" };
  return { label: "Not started", tone: "neutral" };
}

export function DevelopmentView({ world, projectId }: { world: World; projectId: string }) {
  const content = DEVELOPMENT[projectId];
  const items = world.tasks.filter((t) => t.projectId === projectId && t.phase === 9);
  if (!content || items.length === 0) return null;
  const done = items.filter((t) => t.state === "completed").length;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Work packages" value={items.length} />
        <Stat label="Merged" value={done} tone="success" />
        <Stat label="In review" value={items.filter((t) => t.state === "waiting_for_review").length} tone="violet" />
        <Stat label="Failed or blocked" value={items.filter((t) => t.state === "failed" || t.state === "blocked").length} tone="danger" />
      </div>
      <Progress value={(done / items.length) * 100} tone="success" label="Implementation progress" />
      <DataTable<Task>
        rows={items}
        rowKey={(t) => t.id}
        columns={[
          { key: "wi", header: "Work item", render: (t) => <div className="min-w-56"><span className="font-medium">{t.key}</span> {t.title}</div> },
          { key: "agent", header: "Developer", hideBelow: "lg", render: (t) => <span className="text-xs">{byId(world.agents, t.agentId)?.name ?? "Unassigned"}</span> },
          { key: "state", header: "State", render: (t) => <StatusPill size="sm" meta={TASK_STATE[t.state]} /> },
          { key: "build", header: "Build", render: (t) => { const b = buildStatus(world, t); return <Tag tone={b.tone}>{b.label}</Tag>; } },
          { key: "tests", header: "Unit tests", align: "right", render: (t) => { const r = content.tests[t.key]; return r ? <span className={r[0] < r[1] ? "text-danger" : ""}>{r[0]}/{r[1]}</span> : "-"; } },
          { key: "review", header: "Code review", hideBelow: "md", render: (t) => { const r = reviewStatus(t); return <Tag tone={r.tone}>{r.label}</Tag>; } },
        ]}
      />
      <p className="text-2xs text-fg-subtle">Each change set is built and tested in a sandbox VM (simulated here); a reviewer approves it only after its tests pass, then Agentra merges it into main.</p>
    </div>
  );
}

/* Phase 10 ------------------------------------------------------------------------------------------ */

export function QaView({ world, projectId }: { world: World; projectId: string }) {
  const content = QA[projectId];
  if (!content) return null;
  const fixed = byId(world.tasks, "t-i6")?.state === "completed";
  const perfDone = byId(world.tasks, "t-i5")?.state === "completed";
  const suites = content.suites.map((s) =>
    s.name === "Permissions" && fixed ? { ...s, passed: s.cases, failed: 0 } : s.name === "Performance" && perfDone ? { ...s, passed: s.cases, blocked: 0 } : s,
  );
  const defects = content.defects.map((d) => (d.id === "DEF-014" && fixed ? { ...d, status: "retested" as const } : d));
  const total = suites.reduce((n, s) => n + s.cases, 0);
  const passed = suites.reduce((n, s) => n + s.passed, 0);
  const failed = suites.reduce((n, s) => n + s.failed, 0);
  const blocked = suites.reduce((n, s) => n + s.blocked, 0);
  const rate = Math.round((passed / total) * 1000) / 10;
  const met = {
    no_critical: !defects.some((d) => d.severity === "critical" && d.status === "open"),
    pass_rate: rate >= 98,
    performance: perfDone,
    accessibility: byId(world.tasks, "t-i3")?.state === "completed",
  };
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Test cases" value={total} />
        <Stat label="Passed" value={passed} tone="success" />
        <Stat label="Failed" value={failed} tone={failed ? "danger" : "success"} />
        <Stat label="Blocked" value={blocked} tone={blocked ? "warning" : "success"} />
        <Stat label="Pass rate" value={`${rate}%`} tone={rate >= 98 ? "success" : "warning"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <section>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Test execution by suite</h3>
          <ul className="space-y-2">
            {suites.map((s) => (
              <li key={s.name}>
                <div className="flex justify-between text-xs"><span>{s.name}</span><span className="text-fg-subtle tabular">{s.passed}/{s.cases}{s.failed ? ` · ${s.failed} failed` : ""}{s.blocked ? ` · ${s.blocked} blocked` : ""}</span></div>
                <div className="mt-1 flex h-1.5 overflow-hidden rounded-full bg-surface-3">
                  <span className="bg-success" style={{ width: `${(s.passed / s.cases) * 100}%` }} />
                  <span className="bg-danger" style={{ width: `${(s.failed / s.cases) * 100}%` }} />
                  <span className="bg-warning" style={{ width: `${(s.blocked / s.cases) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
        <div className="space-y-4">
          <section>
            <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Defects and retests</h3>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {defects.map((d) => (
                <li key={d.id} className="flex items-center gap-2 px-3 py-1.5 text-xs">
                  <Tag tone={d.severity === "critical" ? "danger" : d.severity === "major" ? "warning" : "neutral"}>{d.severity}</Tag>
                  <span className="font-semibold">{d.id}</span><span className="min-w-0 flex-1 truncate">{d.title}</span>
                  <Tag tone={d.status === "open" ? "danger" : d.status === "retested" ? "success" : d.status === "fixed" ? "primary" : "neutral"}>{d.status}</Tag>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">QA completion criteria</h3>
            <ul className="space-y-1">
              {content.exitCriteria.map((c) => (
                <li key={c.key} className="flex items-center gap-2 text-xs">{met[c.key] ? <CircleCheck className="size-4 text-success" aria-label="Met" /> : <CircleX className="size-4 text-danger" aria-label="Not met" />}{c.text}</li>
              ))}
            </ul>
            <p className="mt-1 text-2xs text-fg-subtle">The QA completion report is approved by a person once every criterion is met.</p>
          </section>
        </div>
      </div>
    </div>
  );
}

/* Phase 11 ------------------------------------------------------------------------------------------ */

export function UatView({ world, projectId }: { world: World; projectId: string }) {
  const content = UAT[projectId];
  if (!content) return null;
  const signoff = byId(world.decisions, "d-uat-signoff");
  const total = content.scenarios.reduce((n, s) => n + s.total, 0);
  const passed = content.scenarios.reduce((n, s) => n + s.passed, 0);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="UAT scenarios" value={total} />
        <Stat label="Passed" value={passed} tone="success" />
        <Stat label="Feedback items" value={content.feedback.length} tone="primary" />
        <Stat label="Sign-off" value={signoff ? DECISION_STATUS[signoff.status].label : "-"} tone={signoff?.status === "approved" ? "success" : "violet"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <section>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">UAT progress by area</h3>
          <ul className="space-y-2">
            {content.scenarios.map((s) => (
              <li key={s.group}>
                <div className="flex justify-between text-xs"><span>{s.group}</span><span className="text-fg-subtle tabular">{s.passed}/{s.total}</span></div>
                <Progress className="mt-1" value={(s.passed / s.total) * 100} tone={s.failed ? "warning" : "success"} label={`${s.group}: ${s.passed} of ${s.total}`} />
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-1.5 text-xs font-semibold text-fg-muted">Customer feedback, defects and change requests</h3>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {content.feedback.map((f) => (
              <li key={f.id} className="flex items-center gap-2 px-3 py-1.5 text-xs">
                <span className="font-semibold">{f.id}</span><span className="min-w-0 flex-1">{f.title}</span>
                <Tag tone={f.type === "defect" ? "danger" : f.type === "change_request" ? "violet" : "neutral"}>{f.type.replace("_", " ")}</Tag>
                <Tag tone={f.status === "closed" ? "success" : "warning"}>{f.status === "proposed_cr" ? "proposed as CR" : f.status}</Tag>
              </li>
            ))}
          </ul>
          {signoff && (
            <Link to={`/decisions?id=${signoff.id}`} className="mt-3 flex items-center justify-between rounded-lg border border-violet/40 bg-violet-soft/40 px-3 py-2 text-[13px] hover:bg-violet-soft">
              <span>Customer acceptance ({signoff.code}): only the customer approver records sign-off</span>
              <StatusPill size="sm" meta={DECISION_STATUS[signoff.status]} />
            </Link>
          )}
        </section>
      </div>
    </div>
  );
}

/* Previews and summaries ---------------------------------------------------------------------------- */

export function PreviewView({ phase }: { phase: number }) {
  const content = PREVIEW[phase];
  if (!content) return <EmptyState title="Preview content arrives later" />;
  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-muted">{content.note}</p>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-[13px]">
          <thead><tr className="border-b border-line">{content.columns.map((c) => <th key={c} className="h-9 px-3 text-left text-2xs font-semibold tracking-wide text-fg-subtle uppercase">{c}</th>)}</tr></thead>
          <tbody>{content.rows.map((row) => <tr key={row.join()} className="border-b border-line last:border-0">{row.map((cell, i) => <td key={i} className="px-3 py-2">{cell}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

/** For a project in a phase without detailed content: where it stands, its tasks and documents for that phase. */
export function PhaseSummary({ world, project, phase }: { world: World; project: Project; phase: number }) {
  const state = project.phases[phase - 1]!;
  const def = phaseDef(phase);
  const docs = world.artifacts.filter((a) => a.projectId === project.id && a.phase === phase);
  const tasks = world.tasks.filter((t) => t.projectId === project.id && t.phase === phase);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <StatusPill meta={PHASE_STATE[state.state]} />
        {state.state === "completed" && state.completedAt && <span className="text-fg-muted">Completed {formatDate(state.completedAt)}; gate passed: {def.gate.toLowerCase()}.</span>}
        {state.state === "upcoming" && <span className="text-fg-muted">Not started; it follows Phase {phase - 1} ({phaseDef(Math.max(1, phase - 1)).short}).</span>}
      </div>
      {tasks.length > 0 && <ul className="space-y-1">{tasks.map((t) => <li key={t.id} className="flex items-center gap-2 text-xs"><Tag>{t.key}</Tag><span className="flex-1">{t.title}</span><StatusPill size="sm" meta={TASK_STATE[t.state]} /></li>)}</ul>}
      {docs.length > 0 && <ul className="space-y-1">{docs.map((d) => <li key={d.id}><DocLink world={world} id={d.id} /></li>)}</ul>}
      {tasks.length === 0 && docs.length === 0 && state.state !== "upcoming" && <p className="text-xs text-fg-subtle">No tasks or documents recorded for this phase in the demo data.</p>}
    </div>
  );
}

/** The phase-specific view for a project, or its summary. */
export function PhaseContent({ world, project, phase }: { world: World; project: Project; phase: number }) {
  const view =
    phase === 7 ? <RequirementsView world={world} projectId={project.id} />
    : phase === 8 ? <ArchitectureView world={world} projectId={project.id} />
    : phase === 9 ? <DevelopmentView world={world} projectId={project.id} />
    : phase === 10 ? <QaView world={world} projectId={project.id} />
    : phase === 11 ? <UatView world={world} projectId={project.id} />
    : null;
  const hasDetail = (phase === 7 && REQUIREMENTS[project.id]) || (phase === 8 && ARCHITECTURE[project.id]) || (phase === 9 && DEVELOPMENT[project.id]) || (phase === 10 && QA[project.id]) || (phase === 11 && UAT[project.id]);
  return (
    <Panel title={`Phase ${phase}: ${phaseDef(phase).name}`} subtitle={project.name}>
      {hasDetail ? view : <PhaseSummary world={world} project={project} phase={phase} />}
    </Panel>
  );
}
