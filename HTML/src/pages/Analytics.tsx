/* S10: Company Performance, Agent Performance and Reports and Analytics. Every figure is computed from the demo
   records; reports preview in the page, download as CSV and print (or save as PDF) from the browser. */
import { useState } from "react";
import { Bot, CalendarClock, ChartColumn, CircleCheck, CircleX, Clock, DollarSign, FileDown, FileText, Gauge, Printer, Scale, TestTubeDiagonal, Timer, Wallet } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { AgentActivityChart, BarList, TaskTrendChart } from "@/components/charts/Charts";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { Progress } from "@/components/ui/States";
import { HEALTH } from "@/components/ui/status";
import { Tabs } from "@/components/ui/Tabs";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { PHASES } from "@/data/lifecycle";
import { duration, formatDateTime, usd } from "@/lib/format";
import { agentRows, approvalTurnaround, projectPerformance, qaMetrics, reportCsv, REPORTS, workforceTotals, type AgentRow } from "@/store/reports";
import { useDemo } from "@/store/useDemo";
import type { ServiceLine } from "@/types";

const SERVICE: Record<ServiceLine, string> = {
  sharepoint_migration: "SharePoint migration", intranet: "Intranet", power_platform: "Power Platform", azure: "Azure", ai: "AI", automation: "Automation",
};

function Select<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as T)} aria-label={label} className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

/* Company Performance --------------------------------------------------------------------------------- */

export function CompanyPerformance() {
  const world = useDemo((s) => s.world);
  const navigate = useNavigate();
  const [service, setService] = useState<ServiceLine | "all">("all");
  const rows = projectPerformance(world).filter((r) => service === "all" || r.project.service === service);
  const milestones = rows.flatMap((r) => r.project.milestones);
  const turnaround = approvalTurnaround(world);
  const totals = workforceTotals(world);
  const qa = qaMetrics();
  const services = [...new Set(world.projects.map((p) => p.service))];
  const gates = PHASES.map((ph) => ({ key: String(ph.number), label: `${ph.number} ${ph.short}`, value: world.projects.filter((p) => p.phases[ph.number - 1]!.state === "completed").length, tone: ph.mvp ? ("primary" as const) : ("neutral" as const) }));

  return (
    <div className="space-y-5">
      <PageHeader title="Company Performance" crumbs={[{ label: "Company command" }]}
        description="Delivery, quality, agent and approval performance across the company. Select a project to drill down."
        actions={<><Select label="Service line" value={service} onChange={setService} options={[["all", "All service lines"], ...services.map((s) => [s, SERVICE[s]] as [ServiceLine, string])]} />
          <Link to="/reports" className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-surface-2 px-3 text-sm hover:bg-surface-3"><FileText className="size-4" aria-hidden />Reports</Link></>} />

      <section aria-label="Performance figures" className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <Kpi label="Average completion" value={`${Math.round(rows.reduce((s, r) => s + r.completion, 0) / Math.max(1, rows.length))}%`} icon={Gauge} hint={`${rows.length} project(s)`} />
        <Kpi label="Milestones met" value={`${milestones.filter((m) => m.done).length}/${milestones.length}`} icon={CalendarClock} tone="cyan" hint={`${milestones.filter((m) => !m.done && Date.parse(m.due) < Date.parse(world.now)).length} late`} />
        <Kpi label="Spending ahead of progress" value={rows.filter((r) => r.budgetUsed > r.completion + 10).length} icon={Wallet} tone="warning" hint="budget used > work done + 10 pts" />
        <Kpi label="Agent success rate" value={`${totals.successRate}%`} icon={Bot} tone="success" onClick={() => navigate("/agents/performance")} hint={`${totals.runs} runs`} />
        <Kpi label="Median approval time" value={turnaround.median === null ? "n/a" : `${turnaround.median} h`} icon={Scale} tone="violet" onClick={() => navigate("/reports?report=approvals")} hint={`${turnaround.open.length} waiting now`} />
        <Kpi label="QA pass rate" value={`${qa.passRate}%`} icon={TestTubeDiagonal} tone="primary" onClick={() => navigate("/reports?report=qa")} hint={`${qa.passed} of ${qa.executed} executed`} />
      </section>

      <Panel title="Project performance" subtitle="Select a project to open it" icon={Gauge} flush>
        <DataTable
          rows={rows}
          rowKey={(r) => r.project.id}
          onRowClick={(r) => navigate(`/projects/${r.project.id}`)}
          columns={[
            { key: "name", header: "Project", sortValue: (r) => r.project.name, render: (r) => <div className="min-w-48"><div className="font-medium">{r.project.name}</div><div className="text-2xs text-fg-subtle">{SERVICE[r.project.service]} · Phase {r.phase}</div></div> },
            { key: "completion", header: "Work done", sortValue: (r) => r.completion, render: (r) => <div className="flex w-36 items-center gap-2"><Progress value={r.completion} label={`${r.project.name} work done`} /><span className="text-xs tabular">{r.completion}%</span></div> },
            { key: "budget", header: "Budget used", sortValue: (r) => r.budgetUsed, render: (r) => <div className="flex w-36 items-center gap-2"><Progress value={r.budgetUsed} tone={r.budgetUsed > r.completion + 10 ? "warning" : "cyan"} label={`${r.project.name} budget used`} /><span className="text-xs tabular">{r.budgetUsed}%</span></div> },
            { key: "milestones", header: "Milestones", hideBelow: "lg", render: (r) => r.milestones },
            { key: "health", header: "Health", sortValue: (r) => r.health, render: (r) => <StatusPill size="sm" meta={HEALTH[r.health]} /> },
          ]}
        />
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Task completion trend" subtitle="Last 14 days, from task records" icon={ChartColumn}><TaskTrendChart world={world} /></Panel>
        <Panel title="Human approval turnaround" subtitle="Hours from raised to decided" icon={Timer} actions={<Link to="/reports?report=approvals" className="text-xs text-primary-strong hover:underline">Report</Link>}>
          <BarList label="Approval turnaround by decision" unit=" h"
            items={[...turnaround.decided.map((d) => ({ key: d.decision.id, label: `${d.decision.code} ${d.decision.title}`, value: d.hours, tone: "violet" as const, to: `/decisions?id=${d.decision.id}` })),
              ...turnaround.open.map((o) => ({ key: o.decision.id, label: `${o.decision.code} ${o.decision.title}`, value: o.hours, tone: "warning" as const, hint: "waiting", to: `/decisions?id=${o.decision.id}` }))].slice(0, 8)} />
        </Panel>
        <Panel title="Phase gates passed" subtitle="Projects that have completed each phase" icon={CircleCheck}><BarList label="Projects past each phase" items={gates} max={world.projects.length} /></Panel>
        <Panel title="Agent execution activity" subtitle="Runs by agent category" icon={Bot}><AgentActivityChart world={world} /></Panel>
      </div>
    </div>
  );
}

/* Agent Performance ----------------------------------------------------------------------------------- */

export function AgentPerformance() {
  const world = useDemo((s) => s.world);
  const navigate = useNavigate();
  const [category, setCategory] = useState("all");
  const totals = workforceTotals(world);
  const all = agentRows(world);
  const rows = all.filter((r) => category === "all" || r.category === category);
  const categories = [...new Set(all.map((r) => r.category))];
  return (
    <div className="space-y-5">
      <PageHeader title="Agent Performance" crumbs={[{ label: "AI workforce" }]} description="Runs, success rates, run times and recorded cost for every agent. Select an agent to open its profile." />
      <section aria-label="Workforce figures" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi label="Runs" value={totals.runs} icon={Bot} hint="all time, from agent records" />
        <Kpi label="Success rate" value={`${totals.successRate}%`} icon={CircleCheck} tone="success" />
        <Kpi label="Failed runs" value={totals.failed} icon={CircleX} tone="danger" onClick={() => navigate("/agents/history")} hint="see execution history" />
        <Kpi label="Average run" value={duration(totals.avgSeconds)} icon={Clock} tone="cyan" />
        <Kpi label="Recorded model cost" value={usd(totals.recordedCost)} icon={DollarSign} tone="violet" hint={`${totals.recordedRuns} recorded runs, simulated`} />
      </section>
      <Tabs value={category} onValueChange={setCategory} items={[{ value: "all", label: "All agents", count: all.length }, ...categories.map((c) => ({ value: c, label: c, count: all.filter((r) => r.category === c).length }))]}>
        <div className="grid gap-5 pt-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <Panel title="Success rate" subtitle="Lowest first" icon={Gauge}>
            <BarList label="Success rate by agent" unit="%" max={100}
              items={[...rows].filter((r) => r.runs > 0).sort((a, b) => a.successRate - b.successRate).map((r) => ({ key: r.agent.id, label: r.agent.name, value: r.successRate, tone: r.successRate < 95 ? ("warning" as const) : ("success" as const), to: `/agents?agent=${r.agent.id}` }))} />
          </Panel>
          <Panel title={`${rows.length} agents`} icon={Bot} flush>
            <DataTable<AgentRow>
              rows={rows}
              rowKey={(r) => r.agent.id}
              onRowClick={(r) => navigate(`/agents?agent=${r.agent.id}`)}
              columns={[
                { key: "agent", header: "Agent", sortValue: (r) => r.agent.name, render: (r) => <span className="flex items-center gap-2 whitespace-nowrap"><Avatar name={r.agent.name} agent size="sm" />{r.agent.name}</span> },
                { key: "category", header: "Category", hideBelow: "2xl", sortValue: (r) => r.category, render: (r) => r.category },
                { key: "runs", header: "Runs", align: "right", sortValue: (r) => r.runs, render: (r) => r.runs },
                { key: "failed", header: "Failed", align: "right", sortValue: (r) => r.failed, render: (r) => <span className={cn(r.failed > 5 && "text-warning")}>{r.failed}</span> },
                { key: "rate", header: "Success", align: "right", sortValue: (r) => r.successRate, render: (r) => `${r.successRate}%` },
                { key: "avg", header: "Avg run", align: "right", hideBelow: "lg", sortValue: (r) => r.avgSeconds, render: (r) => duration(r.avgSeconds) },
                { key: "cost", header: "Recorded cost", align: "right", hideBelow: "xl", sortValue: (r) => r.recordedCost, render: (r) => usd(r.recordedCost) },
              ]}
            />
          </Panel>
        </div>
      </Tabs>
      <p className="text-2xs text-fg-subtle">Run counts and success rates come from each agent's record. Cost covers only the runs recorded in this demo; {Object.keys(CATEGORY_LABELS).length} categories.</p>
    </div>
  );
}

/* Reports and Analytics ------------------------------------------------------------------------------- */

function download(fileName: string, text: string): void {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function Reports() {
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const [projectId, setProjectId] = useState(() => params.get("project") ?? "all"); // a project's Reports tab links here with ?project=
  const action = useRuleAction();
  const report = REPORTS.find((r) => r.id === params.get("report")) ?? REPORTS[0]!;
  const body = report.build(world, report.projectFilter ? projectId : "all");
  const select = (id: string) => {
    action.clear();
    setParams((p) => { p.set("report", id); return p; });
  };
  const fileName = `agentra-${report.id}-${world.now.slice(0, 10)}.csv`;

  return (
    <div className="space-y-5">
      <PageHeader title="Reports and Analytics" crumbs={[{ label: "Intelligence" }]}
        description="Reports built from the records at this moment of the simulation. Preview them here, download the data as CSV, or print or save them as PDF." />
      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Panel title="Reports" icon={FileText} flush>
          <ul aria-label="Report catalogue" className="divide-y divide-line">
            {REPORTS.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => select(r.id)} aria-pressed={r.id === report.id}
                  className={cn("w-full px-4 py-2.5 text-left hover:bg-surface-2", r.id === report.id && "bg-surface-2")}>
                  <span className="block text-[13px] font-medium">{r.title}</span>
                  <span className="block text-2xs text-fg-subtle">{r.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2" data-print-hide>
            {report.projectFilter ? (
              <Select label="Project" value={projectId} onChange={setProjectId} options={[["all", "All projects"], ...world.projects.map((p) => [p.id, p.name] as [string, string])]} />
            ) : <span className="text-xs text-fg-subtle">This report covers the whole company.</span>}
            <div className="ml-auto flex gap-2">
              <Button size="sm" icon={FileDown} onClick={() => action.run(() => download(fileName, reportCsv(report.title, body)), `Downloaded ${fileName}`)}>Download CSV</Button>
              <Button size="sm" icon={Printer} onClick={() => action.run(() => window.print(), "Opened the print dialog. Choose Save as PDF to export.")}>Print or save as PDF</Button>
            </div>
          </div>
          {action.error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger" data-print-hide>{action.error}</p>}
          {action.done && <p role="status" className="rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-success" data-print-hide>{action.done}</p>}

          <article aria-label={`${report.title} preview`} data-print-root className="rounded-[var(--radius-panel)] border border-line bg-surface p-6 shadow-panel">
            <header className="border-b border-line pb-4">
              <p className="text-2xs font-semibold tracking-wide text-fg-subtle uppercase">Agentra · {report.audience}</p>
              <h2 className="mt-1 text-lg font-semibold">{report.title}{report.projectFilter && projectId !== "all" ? `: ${world.projects.find((p) => p.id === projectId)?.name}` : ""}</h2>
              <p className="mt-1 text-[13px] text-fg-muted">{body.summary}</p>
              <p className="mt-2 text-2xs text-fg-subtle">Generated {formatDateTime(world.now)} (simulated clock) from the demo records.</p>
            </header>
            {body.figures.length > 0 && (
              <dl className="grid grid-cols-2 gap-3 border-b border-line py-4 sm:grid-cols-4">
                {body.figures.map((f) => <div key={f.label}><dt className="text-2xs text-fg-subtle">{f.label}</dt><dd className="text-lg font-semibold tabular">{f.value}</dd></div>)}
              </dl>
            )}
            {body.placeholder && <p className="mt-4 rounded-lg border border-dashed border-warning/50 bg-warning-soft/30 px-3 py-2 text-xs text-fg-muted"><Tag tone="warning" className="mr-1.5">Placeholder</Tag>{body.placeholder}</p>}
            {body.sections.map((section) => (
              <section key={section.heading} className="mt-5">
                <h3 className="mb-2 text-sm font-semibold">{section.heading}</h3>
                {section.text && <p className="text-[13px] text-fg-muted">{section.text}</p>}
                {section.table && (section.table.rows.length === 0 ? <p className="text-[13px] text-fg-subtle">None.</p> : (
                  <div className="overflow-x-auto rounded-lg border border-line">
                    <table className="w-full text-xs">
                      <thead><tr className="border-b border-line">{section.table.columns.map((c) => <th key={c} scope="col" className="px-3 py-2 text-left text-2xs font-semibold tracking-wide text-fg-subtle uppercase">{c}</th>)}</tr></thead>
                      <tbody>{section.table.rows.map((row, i) => <tr key={i} className="border-b border-line last:border-0">{row.map((cell, j) => <td key={j} className={cn("px-3 py-2 align-top", typeof cell === "number" && "text-right tabular")}>{cell}</td>)}</tr>)}</tbody>
                    </table>
                  </div>
                ))}
              </section>
            ))}
          </article>
        </div>
      </div>
    </div>
  );
}
