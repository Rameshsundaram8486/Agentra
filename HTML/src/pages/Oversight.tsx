/* S09: the Project Owner Agent's workspace, Project Health and Risk and Compliance. The agent monitors and recommends;
   every figure here is read from records, every recommendation is labelled as the agent's proposal, and people act. */
import {
  Ban, BrainCircuit, CalendarClock, CircleCheck, CircleX, Clock, Gauge, Hand, Microscope, Radar, Scale, ShieldCheck, TriangleExclamationPoint, Wallet,
} from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { RiskMatrix } from "@/components/charts/Charts";
import { FindingRow, ScoreRing, SourceTag, STATUS } from "@/components/dashboard/OwnerBriefing";
import { PageHeader } from "@/components/layout/PageHeader";
import { RcaDetail, RcaList } from "@/components/oversight/RcaWorkspace";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Drawer } from "@/components/ui/Overlays";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState, Progress } from "@/components/ui/States";
import { HEALTH, INCIDENT_STATUS, RISK_STATUS, TONE_TEXT } from "@/components/ui/status";
import { phaseDef } from "@/data/lifecycle";
import { formatDate, formatDateTime, relative } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { briefing } from "@/store/briefing";
import { burn, complianceChecks, delays, failedRuns, healthSignals, stuckWork } from "@/store/oversight";
import { actorName, byId, currentPhase, isOverdue, OPEN_INCIDENT, projectHealth, riskLevel, riskScore } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Risk, World } from "@/types";

function useParam(key: string): [string | null, (value: string | null) => void] {
  const [params, setParams] = useSearchParams();
  return [params.get(key), (value) => setParams((p) => { if (value) p.set(key, value); else p.delete(key); return p; })];
}

/* Project Owner Agent --------------------------------------------------------------------------------- */

export function ProjectOwnerAgent() {
  const world = useDemo((s) => s.world);
  const [incidentId, setIncident] = useParam("incident");
  const brief = briefing(world);
  const owner = world.agents.find((a) => a.typeKey === "project_owner");
  const runs = failedRuns(world);
  const stuck = stuckWork(world);
  const late = delays(world);
  const overdue = world.decisions.filter((d) => isOverdue(d, world.now));
  const active = world.projects.filter((p) => p.status === "active");
  const incident = byId(world.incidents, incidentId ?? undefined) ?? world.incidents.find((i) => (OPEN_INCIDENT as readonly string[]).includes(i.status)) ?? world.incidents[0];
  const openIncidents = world.incidents.filter((i) => (OPEN_INCIDENT as readonly string[]).includes(i.status));

  return (
    <div className="space-y-5">
      <PageHeader title="Project Owner Agent" crumbs={[{ label: "AI workforce" }]}
        description="Watches every project, run and decision; finds what is going wrong and recommends what to do. It cannot approve or decide: people do."
        meta={owner && <Tag tone="violet" icon={Radar}>{owner.name} · {owner.status === "working" ? "scanning now" : `last active ${relative(owner.since, world.now)}`}</Tag>} />

      <section aria-label="Monitoring overview" className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Panel title="Company health" icon={Gauge} actions={<SourceTag kind="record" />}>
          <div className="flex items-center gap-4">
            <ScoreRing score={brief.score} status={brief.status} />
            <div>
              <p className={cn("text-sm font-semibold", TONE_TEXT[STATUS[brief.status].tone])}>{STATUS[brief.status].label}</p>
              <p className="text-[13px] text-fg-muted">{brief.headline}</p>
            </div>
          </div>
          <p className="mt-3 text-2xs text-fg-subtle">Score: 100 less 15 per critical project, 8 per project at risk, 6 per overdue decision, 4 per open incident and 2 per failed or blocked task.</p>
        </Panel>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Kpi label="Projects needing attention" value={active.filter((p) => ["critical", "at_risk"].includes(projectHealth(world, p).health)).length} icon={TriangleExclamationPoint} tone="warning" hint={`of ${active.length} active`} />
          <Kpi label="Failed agent runs" value={runs.length} icon={CircleX} tone="danger" hint={`${runs.filter((r) => r.incident).length} with an incident`} />
          <Kpi label="Stuck work" value={stuck.length} icon={Ban} tone="warning" hint="failed, blocked or waiting > 24 h" />
          <Kpi label="Overdue decisions" value={overdue.length} icon={Scale} tone={overdue.length ? "danger" : "success"} hint="past their deadline" />
          <Kpi label="Milestone delays" value={late.length} icon={CalendarClock} tone="warning" hint={`${late.filter((d) => d.kind === "late").length} late, ${late.filter((d) => d.kind === "at_risk").length} at risk`} />
          <Kpi label="Open incidents" value={openIncidents.length} icon={Microscope} tone="danger" hint="with root-cause analyses" />
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Health assessment by project" icon={Gauge} flush actions={<Link to="/health" className="text-xs text-primary-strong hover:underline">Project Health</Link>}>
          <ul className="divide-y divide-line">
            {active.map((p) => {
              const h = projectHealth(world, p);
              return (
                <li key={p.id}><Link to={`/health?project=${p.id}`} className="flex items-start gap-3 px-4 py-2.5 hover:bg-surface-2">
                  <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium">{p.name}</span><span className="block truncate text-2xs text-fg-subtle">{h.reasons[0]}</span></span>
                  <StatusPill size="sm" meta={HEALTH[h.health]} />
                </Link></li>
              );
            })}
          </ul>
        </Panel>
        <Panel title="Recommended corrective actions" subtitle="Proposals for people to decide" icon={BrainCircuit} flush actions={<SourceTag kind="ai" />}>
          {brief.actions.length === 0 ? <EmptyState icon={CircleCheck} title="No corrective actions recommended" /> : (
            <ul className="divide-y divide-line">
              {brief.actions.map((a) => (
                <li key={a.text}><Link to={a.link} className="block px-4 py-2.5 hover:bg-surface-2">
                  <span className="block text-[13px]">{a.text}</span>
                  <span className="mt-0.5 block text-2xs text-fg-subtle">Based on {a.basis} · for {ROLE_LABELS[a.owner].toLowerCase()}</span>
                </Link></li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
        <Panel title="Detected risks" icon={ShieldCheck} flush actions={<Link to="/risk" className="text-xs text-primary-strong hover:underline">Risk register</Link>}>
          <ul className="divide-y divide-line">
            {brief.risks.map((r) => (
              <li key={r.id} className="flex items-start gap-2 px-4 py-2.5 text-[13px]">
                <Tag>{r.code}</Tag><span className="min-w-0 flex-1">{r.title}<span className="block text-2xs text-fg-subtle">Detected by {actorName(world, r.detectedBy)} · score {riskScore(r)}</span></span>
                <StatusPill size="sm" meta={RISK_STATUS[r.status]} />
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Failed agent executions" icon={CircleX} flush actions={<Link to="/agents/history" className="text-xs text-primary-strong hover:underline">All runs</Link>}>
          {runs.length === 0 ? <EmptyState icon={CircleCheck} title="No failed runs" /> : (
            <ul className="divide-y divide-line">
              {runs.map(({ execution, incident: inc }) => (
                <li key={execution.id} className="px-4 py-2.5 text-[13px]">
                  <Link to={`/agents/history?run=${execution.id}`} className="hover:text-primary-strong">{execution.title}</Link>
                  <span className="block text-2xs text-fg-subtle">{actorName(world, execution.agentId)} · attempt {execution.attempt} of {execution.maxAttempts} · {relative(execution.endedAt ?? execution.startedAt, world.now)}</span>
                  {inc && <button type="button" onClick={() => setIncident(inc.id)} className="mt-1 text-2xs text-primary-strong hover:underline">{inc.code}: root-cause analysis</button>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Stuck workflows" icon={Ban} flush>
          {stuck.length === 0 ? <EmptyState icon={CircleCheck} title="Nothing is stuck" /> : (
            <ul className="divide-y divide-line">
              {stuck.map((s) => (
                <li key={s.task.id}><Link to={s.link} className="block px-4 py-2.5 text-[13px] hover:bg-surface-2">
                  <span className="flex items-center gap-2"><Tag>{s.task.key}</Tag><span className="min-w-0 flex-1 truncate">{s.task.title}</span></span>
                  <span className="mt-0.5 block text-2xs text-fg-subtle">{s.reason} · {s.hours} h · {byId(world.projects, s.task.projectId)?.code}</span>
                </Link></li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Overdue decisions" icon={Clock} flush>
          {overdue.length === 0 ? <EmptyState icon={CircleCheck} title="No decision is overdue" /> : (
            <ul className="divide-y divide-line">
              {overdue.map((d) => (
                <li key={d.id}><Link to={`/decisions?id=${d.id}`} className="block px-4 py-2.5 text-[13px] hover:bg-surface-2">
                  <span className="flex items-center gap-2"><Tag>{d.code}</Tag>{d.title}</span>
                  <span className="mt-0.5 block text-2xs text-danger">Due {formatDateTime(d.deadline)} · decides: {d.allowedRoles.map((r) => ROLE_LABELS[r]).join(" or ")}</span>
                </Link></li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Project delays" subtitle="Late milestones, and milestones due within 7 days on projects at risk" icon={CalendarClock} flush className="lg:col-span-2">
          {late.length === 0 ? <EmptyState icon={CircleCheck} title="No delays detected" /> : (
            <ul className="divide-y divide-line">
              {late.map((d) => (
                <li key={d.milestone.id}><Link to="/milestones" className="flex items-start gap-3 px-4 py-2.5 text-[13px] hover:bg-surface-2">
                  <Tag tone={d.kind === "late" ? "danger" : "warning"} className="mt-px">{d.kind === "late" ? "Late" : "At risk"}</Tag>
                  <span className="min-w-0 flex-1">{d.milestone.title}<span className="block text-2xs text-fg-subtle">{d.project.name} · due {formatDate(d.milestone.due)} ({relative(d.milestone.due, world.now)}) · {d.reason}</span></span>
                </Link></li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Root-cause analysis workspace" subtitle="Confirmed facts and AI hypotheses are kept apart" icon={Microscope}>
        <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <RcaList world={world} selectedId={incident?.id} onSelect={setIncident} />
          {incident ? <RcaDetail world={world} incident={incident} /> : <EmptyState title="Select an incident" />}
        </div>
      </Panel>

      <Panel title="All findings" subtitle="Read from records on every change" icon={Hand} actions={<SourceTag kind="record" />}>
        <ul className="grid gap-x-6 md:grid-cols-2">{brief.findings.map((f) => <FindingRow key={f.text} finding={f} />)}</ul>
      </Panel>
    </div>
  );
}

/* Project Health -------------------------------------------------------------------------------------- */

export function ProjectHealth() {
  const world = useDemo((s) => s.world);
  const [projectId, setProject] = useParam("project");
  const project = byId(world.projects, projectId ?? undefined) ?? world.projects.find((p) => projectHealth(world, p).health === "critical") ?? world.projects[0]!;
  const health = projectHealth(world, project);
  const signals = healthSignals(world, project);
  const b = burn(project);
  return (
    <div className="space-y-5">
      <PageHeader title="Project Health" crumbs={[{ label: "Intelligence" }]}
        description="Each project's health and the records behind it. Health is never typed in: it is derived from open risks, incidents, failed or blocked work and overdue decisions." />
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Panel title="Projects" icon={Gauge} flush>
          <ul aria-label="Projects" className="divide-y divide-line">
            {world.projects.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => setProject(p.id)} aria-pressed={p.id === project.id}
                  className={cn("flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2", p.id === project.id && "bg-surface-2")}>
                  <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium">{p.name}</span><span className="block text-2xs text-fg-subtle">Phase {currentPhase(p).phase}, {phaseDef(currentPhase(p).phase).short}</span></span>
                  <StatusPill size="sm" meta={HEALTH[projectHealth(world, p).health]} />
                </button>
              </li>
            ))}
          </ul>
        </Panel>
        <div className="space-y-5">
          <Panel title={project.name} subtitle={`${byId(world.customers, project.customerId)?.name} · managed by ${actorName(world, project.managerId)}`} icon={Gauge}
            actions={<Link to={`/projects/${project.id}`} className="text-xs text-primary-strong hover:underline">Open project</Link>}>
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill meta={HEALTH[health.health]} />
              <span className="text-[13px] text-fg-muted">{health.reasons[0]}</span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <p className="flex items-center justify-between text-xs"><span className="text-fg-muted">Work done</span><span className="font-medium tabular">{b.done}%</span></p>
                <Progress value={b.done} label="Work done" className="mt-1" />
              </div>
              <div>
                <p className="flex items-center justify-between text-xs"><span className="flex items-center gap-1 text-fg-muted"><Wallet className="size-3" aria-hidden />Budget used</span><span className={cn("font-medium tabular", b.ahead && "text-warning")}>{b.spent}%</span></p>
                <Progress value={b.spent} tone={b.ahead ? "warning" : "primary"} label="Budget used" className="mt-1" />
              </div>
            </div>
            {b.ahead && <p className="mt-2 text-xs text-warning">Spending is more than 10 points ahead of progress.</p>}
          </Panel>
          <section aria-label="Health signals" className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
            {signals.map((s) => (
              <Link key={s.label} to={s.link} className={cn("rounded-[var(--radius-panel)] border bg-surface p-3.5 shadow-panel hover:bg-surface-2", s.count && s.tone !== "neutral" ? (s.tone === "danger" ? "border-danger/40" : "border-warning/40") : "border-line")}>
                <span className="flex items-center justify-between text-xs text-fg-muted">{s.label}<span className={cn("text-xl font-semibold tabular", s.count && s.tone !== "neutral" ? TONE_TEXT[s.tone] : "text-fg")}>{s.count}</span></span>
                {s.detail.length > 0 ? <ul className="mt-2 space-y-0.5 text-2xs text-fg-subtle">{s.detail.slice(0, 3).map((d) => <li key={d} className="truncate">{d}</li>)}</ul> : <p className="mt-2 text-2xs text-fg-subtle">None</p>}
              </Link>
            ))}
          </section>
          <Panel title="Milestones" icon={CalendarClock} flush>
            <ul className="divide-y divide-line">
              {project.milestones.map((m) => {
                const late = !m.done && Date.parse(m.due) < Date.parse(world.now);
                return (
                  <li key={m.id} className="flex items-center gap-3 px-4 py-2.5 text-[13px]">
                    {m.done ? <CircleCheck className="size-4 text-success" aria-label="Done" /> : late ? <Clock className="size-4 text-danger" aria-label="Late" /> : <Clock className="size-4 text-fg-subtle" aria-label="Upcoming" />}
                    <span className="min-w-0 flex-1">{m.title}<span className="block text-2xs text-fg-subtle">Phase {m.phase} · due {formatDate(m.due)} ({relative(m.due, world.now)})</span></span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* Risk and Compliance --------------------------------------------------------------------------------- */

function RiskDrawer({ world, risk, onClose }: { world: World; risk?: Risk; onClose: () => void }) {
  const data = useDataService();
  const role = useDemo((s) => s.role);
  const action = useRuleAction();
  if (!risk) return <Drawer open={false} onOpenChange={() => onClose()} title="Risk">{null}</Drawer>;
  const run = (c: "mitigate" | "close" | "reopen", done: string) => action.run(() => data.updateRisk(risk.id, c), done);
  return (
    <Drawer open onOpenChange={(o) => !o && onClose()} title={`${risk.code} ${risk.title}`} description={<span className="inline-flex gap-1.5"><StatusPill size="sm" meta={RISK_STATUS[risk.status]} /><Tag>{riskLevel(risk)} · score {riskScore(risk)}</Tag></span>}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="text-2xs text-fg-subtle">Acting as {ROLE_LABELS[role].toLowerCase()}. Simulated.</span>
          <div className="flex gap-2">
            {risk.status === "open" && <Button size="sm" variant="primary" onClick={() => run("mitigate", "Mitigation started.")}>Start mitigating</Button>}
            {risk.status === "mitigating" && <Button size="sm" variant="primary" onClick={() => run("close", "Risk closed.")}>Close risk</Button>}
            {risk.status !== "open" && <Button size="sm" onClick={() => run("reopen", "Risk reopened.")}>Reopen</Button>}
          </div>
        </div>
      }>
      <div className="space-y-4">
        {action.error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger">{action.error}</p>}
        {action.done && <p role="status" className="rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-success">{action.done}</p>}
        <dl className="grid grid-cols-2 gap-3">
          <Field label="Project">{byId(world.projects, risk.projectId)?.name}</Field>
          <Field label="Category">{risk.category}</Field>
          <Field label="Likelihood × impact">{risk.likelihood} × {risk.impact} = {riskScore(risk)}</Field>
          <Field label="Owner"><span className="inline-flex items-center gap-1.5"><Avatar name={actorName(world, risk.ownerId)} size="sm" />{actorName(world, risk.ownerId)}</span></Field>
          <Field label="Detected by">{actorName(world, risk.detectedBy)}, {formatDateTime(risk.detectedAt)}</Field>
        </dl>
        <div><h3 className="mb-1 text-xs font-semibold text-fg-muted">Mitigation</h3><p className="rounded-lg bg-surface-2 px-3 py-2 text-[13px]">{risk.mitigation}</p></div>
      </div>
    </Drawer>
  );
}

export function RiskCompliance() {
  const world = useDemo((s) => s.world);
  const [riskId, setRisk] = useParam("risk");
  const open = world.risks.filter((r) => r.status !== "closed");
  const checks = complianceChecks(world);
  return (
    <div className="space-y-5">
      <PageHeader title="Risk and Compliance" crumbs={[{ label: "Intelligence" }]}
        description="The risk register, incidents and the governance rules Agentra enforces, checked against the records as they are now." />
      <section aria-label="Risk summary" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi label="Open risks" value={open.length} icon={TriangleExclamationPoint} tone="warning" />
        <Kpi label="High or critical" value={open.filter((r) => riskScore(r) >= 12).length} icon={ShieldCheck} tone="danger" hint="score 12 or more" />
        <Kpi label="Being mitigated" value={world.risks.filter((r) => r.status === "mitigating").length} icon={Clock} tone="primary" />
        <Kpi label="Open incidents" value={world.incidents.filter((i) => (OPEN_INCIDENT as readonly string[]).includes(i.status)).length} icon={Microscope} tone="danger" />
        <Kpi label="Governance checks" value={`${checks.filter((c) => c.passed).length}/${checks.length}`} icon={Scale} tone={checks.every((c) => c.passed) ? "success" : "warning"} hint="passing now" />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel title="Risk register" subtitle="Select a risk to update it" icon={ShieldCheck} flush>
          <DataTable<Risk>
            rows={[...world.risks].sort((a, b) => riskScore(b) - riskScore(a))}
            rowKey={(r) => r.id}
            onRowClick={(r) => setRisk(r.id)}
            selectedKey={riskId ?? undefined}
            columns={[
              { key: "code", header: "Risk", sortValue: (r) => r.code, render: (r) => <Tag>{r.code}</Tag> },
              { key: "title", header: "Title", render: (r) => <div className="min-w-48"><div>{r.title}</div><div className="text-2xs text-fg-subtle">{byId(world.projects, r.projectId)?.name}</div></div> },
              { key: "category", header: "Category", hideBelow: "lg", sortValue: (r) => r.category, render: (r) => r.category },
              { key: "score", header: "Score", align: "right", sortValue: riskScore, render: (r) => <span className={cn("font-medium", riskScore(r) >= 16 ? "text-danger" : riskScore(r) >= 12 ? "text-warning" : "")}>{riskScore(r)}</span> },
              { key: "owner", header: "Owner", hideBelow: "xl", render: (r) => actorName(world, r.ownerId) },
              { key: "status", header: "Status", sortValue: (r) => r.status, render: (r) => <StatusPill size="sm" meta={RISK_STATUS[r.status]} /> },
            ]}
          />
        </Panel>
        <Panel title="Risk matrix" subtitle="Open risks by likelihood and impact" icon={ShieldCheck}><RiskMatrix world={world} /></Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Governance checks" subtitle="Checked against the records on every change" icon={Scale} flush>
          <ul className="divide-y divide-line">
            {checks.map((c) => (
              <li key={c.id}><Link to={c.link} className="flex items-start gap-3 px-4 py-2.5 hover:bg-surface-2">
                {c.passed ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-label="Passing" /> : <TriangleExclamationPoint className="mt-0.5 size-4 shrink-0 text-warning" aria-label="Needs attention" />}
                <span className="min-w-0 flex-1 text-[13px]">{c.title}<span className="block text-2xs text-fg-subtle">{c.detail}</span></span>
              </Link></li>
            ))}
          </ul>
        </Panel>
        <Panel title="Incidents" subtitle="Each with a root-cause analysis" icon={Microscope} flush>
          <ul className="divide-y divide-line">
            {world.incidents.map((i) => (
              <li key={i.id}><Link to={`/owner?incident=${i.id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2">
                <Tag>{i.code}</Tag>
                <span className="min-w-0 flex-1 text-[13px]">{i.title}<span className="block text-2xs text-fg-subtle">{byId(world.projects, i.projectId)?.name} · {i.rca.causeConfirmedBy ? "cause confirmed" : `hypothesis, ${i.rca.confidence} confidence`}</span></span>
                <StatusPill size="sm" meta={INCIDENT_STATUS[i.status]} />
              </Link></li>
            ))}
          </ul>
        </Panel>
      </div>
      <RiskDrawer world={world} risk={byId(world.risks, riskId ?? undefined)} onClose={() => setRisk(null)} />
    </div>
  );
}
