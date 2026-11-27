/* S13 Settings and Governance: agent configuration and autonomy, workflow configuration and approval policies, users
   and permissions, and system settings with notification preferences and the audit log. Policies are transcribed
   from the backend's config/ files and shown with their source; agents never approve, and that is not configurable. */
import { useState } from "react";
import {
  Ban, Bell, Bot, CircleCheck, Download, FileCode, GitBranch, KeyRound, Lock, Scale, ScrollText, Search, ShieldCheck, SlidersHorizontal, UserRound, Users, Workflow,
} from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { DataTable } from "@/components/ui/DataTable";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { CATEGORY_LABELS } from "@/data/agentTypes";
import { PHASES } from "@/data/lifecycle";
import {
  actionsFor, APPROVAL_MATRIX, AUTONOMY_LEVELS, AUTONOMY_RANK, CHANGE_SET_RULES, CHANNELS, MAX_FOR_RISK, NOTIFICATION_EVENTS, PERMISSIONS, ROLE_PERMISSIONS, SEPARATION_OF_DUTIES,
} from "@/data/seed/platform";
import { formatDateTime } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { actorName, byId } from "@/store/selectors";
import { ROLE_PEOPLE, useDemo } from "@/store/useDemo";
import type { AuditEntry, Autonomy, Role } from "@/types";

const ROLES: Role[] = ["owner", "project_manager", "reviewer", "customer_approver"];
const AUTONOMY_TONE = { supervised: "violet", controlled: "primary", conditional: "cyan" } as const;

/* Agent Configuration --------------------------------------------------------------------------------- */

export function AgentConfiguration() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const data = useDataService();
  const action = useRuleAction();
  const [params, setParams] = useSearchParams();
  const type = world.agentTypes.find((t) => t.key === params.get("agent")) ?? world.agentTypes.find((t) => t.key === "qa_tester")!;
  const actions = actionsFor(type.key, type.autonomy);
  const version = world.settings.configVersions[type.key] ?? 1;
  const history = world.audit.filter((a) => a.action === "agent_config.autonomy" && a.target === type.name);

  return (
    <div className="space-y-5">
      <PageHeader title="Agent Configuration" crumbs={[{ label: "Administration" }]}
        description="What each agent may do, at which autonomy level. Autonomy is set per action and risk class, not as one switch per agent; approving or deciding is never an agent's." />

      <section aria-label="Autonomy levels" className="grid gap-4 lg:grid-cols-3">
        {AUTONOMY_LEVELS.map((l) => (
          <article key={l.level} aria-label={l.name} className="rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel">
            <Tag tone={AUTONOMY_TONE[l.level]}>{l.name}</Tag>
            <p className="mt-2 text-[13px] font-medium">{l.definition}</p>
            <p className="mt-2 text-xs text-fg-muted"><span className="text-fg-subtle">People: </span>{l.people}</p>
            <p className="mt-1 text-xs text-fg-muted"><span className="text-fg-subtle">Example: </span>{l.example}</p>
          </article>
        ))}
      </section>
      <p className="text-2xs text-fg-subtle">From the governance specification. A fourth level, mature operations, comes after the MVP. Highest level by risk class: low → conditional, medium → controlled, high → supervised.</p>

      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Panel title="Agents" icon={Bot} flush>
          <ul aria-label="Agents" className="max-h-[640px] divide-y divide-line overflow-y-auto">
            {world.agentTypes.map((t) => (
              <li key={t.key}>
                <button type="button" onClick={() => { action.clear(); setParams((p) => { p.set("agent", t.key); return p; }); }} aria-pressed={t.key === type.key}
                  className={cn("flex w-full items-center gap-2.5 px-4 py-2 text-left hover:bg-surface-2", t.key === type.key && "bg-surface-2")}>
                  <Avatar name={t.name} agent size="sm" />
                  <span className="min-w-0 flex-1"><span className="block truncate text-[13px]">{t.name}</span><span className="block text-2xs text-fg-subtle">{CATEGORY_LABELS[t.category].replace(" agents", "")}{t.inMvp ? "" : " · Preview"}</span></span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="space-y-5">
          <Panel title={type.name} subtitle={`config/agents/${type.key}/agent.yaml · version ${version}`} icon={FileCode}
            actions={<Link to={`/agents/directory`} className="text-xs text-primary-strong hover:underline">Agent Directory</Link>}>
            <p className="text-[13px]">{type.description}</p>
            <dl className="mt-3 grid gap-3 sm:grid-cols-4">
              <Field label="Phases">{type.phases.length ? type.phases.join(", ") : "Company-wide"}</Field>
              <Field label="Model">{type.model} · effort {type.effort}</Field>
              <Field label="Default autonomy"><Tag tone={AUTONOMY_TONE[type.autonomy]}>{type.autonomy}</Tag></Field>
              <Field label="Scope">{type.inMvp ? "MVP" : "Preview"}</Field>
            </dl>
            <div className="mt-3"><p className="text-2xs font-medium tracking-wide text-fg-subtle uppercase">Tool allowlist</p><div className="mt-1 flex flex-wrap gap-1.5">{type.tools.map((t) => <Tag key={t}>{t}</Tag>)}</div></div>
          </Panel>

          <Panel title="Actions and autonomy" subtitle={`Acting as ${ROLE_LABELS[role].toLowerCase()}; only the owner changes autonomy`} icon={SlidersHorizontal} flush>
            {action.error && <p role="alert" className="mx-4 mt-3 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger">{action.error}</p>}
            {action.done && <p role="status" className="mx-4 mt-3 rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-success">{action.done}</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead><tr className="border-b border-line text-left text-2xs tracking-wide text-fg-subtle uppercase"><th className="px-4 py-2">Action</th><th className="px-3 py-2">Risk</th><th className="px-3 py-2">Autonomy</th><th className="px-3 py-2">Highest allowed</th></tr></thead>
                <tbody>
                  {actions.map((a) => {
                    const current = world.settings.autonomy[`${type.key}.${a.key}`] ?? a.autonomy;
                    const max = MAX_FOR_RISK[a.risk];
                    return (
                      <tr key={a.key} className="border-b border-line align-top">
                        <td className="px-4 py-2.5">{a.title}{a.condition && <span className="block text-2xs text-fg-subtle">Precondition: {a.condition}</span>}</td>
                        <td className="px-3 py-2.5"><Tag tone={a.risk === "high" ? "danger" : a.risk === "medium" ? "warning" : "neutral"}>{a.risk}</Tag></td>
                        <td className="px-3 py-2.5">
                          <select aria-label={`Autonomy for ${a.title}`} value={current}
                            onChange={(e) => { const level = e.target.value as Autonomy; action.run(() => data.setAutonomy(type.key, a.key, level), `"${a.title}" is now ${level}; the agent definition is version ${version + 1}.`); }}
                            className="h-8 rounded-lg border border-line bg-surface px-2 text-[13px]">
                            {(Object.keys(AUTONOMY_RANK) as Autonomy[]).map((l) => <option key={l} value={l}>{AUTONOMY_LEVELS.find((x) => x.level === l)!.name}{AUTONOMY_RANK[l] > AUTONOMY_RANK[max] ? " (not allowed)" : ""}</option>)}
                          </select>
                        </td>
                        <td className="px-3 py-2.5"><Tag tone={AUTONOMY_TONE[max]}>{max}</Tag></td>
                      </tr>
                    );
                  })}
                  <tr className="align-top">
                    <td className="px-4 py-2.5">Approve, sign off or decide<span className="block text-2xs text-fg-subtle">config/policies/separation_of_duties.yaml</span></td>
                    <td className="px-3 py-2.5"><Tag tone="danger">high</Tag></td>
                    <td className="px-3 py-2.5" colSpan={2}><span className="inline-flex items-center gap-1.5 text-danger"><Ban className="size-3.5" aria-hidden />Never: people only. Not configurable.</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Configuration history" subtitle="Every change is a new version, recorded in the audit log" icon={GitBranch} flush>
            {history.length === 0 ? <EmptyState icon={GitBranch} title={`No changes to ${type.name} in this demo`} hint="Change an action's autonomy above and it appears here." /> : (
              <ul className="divide-y divide-line">{history.map((h) => <li key={h.id} className="px-4 py-2.5 text-[13px]">{h.detail}<span className="block text-2xs text-fg-subtle">{actorName(world, h.actor)} · {formatDateTime(h.at)}</span></li>)}</ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* Workflow Configuration ------------------------------------------------------------------------------ */

const PHASE_FILES: Record<number, { file: string; version?: number; exit?: string }> = {
  1: { file: "phase_01_sales_and_lead_generation" }, 2: { file: "phase_02_meeting_scheduling_and_customer_discovery" }, 3: { file: "phase_03_technical_and_commercial_proposal" },
  4: { file: "phase_04_customer_presentation_and_negotiation" }, 5: { file: "phase_05_project_award_and_po_validation" }, 6: { file: "phase_06_project_kickoff_and_governance" },
  7: { file: "phase_07_business_analysis_and_requirements", version: 1, exit: "requirements_baseline" },
  8: { file: "phase_08_solution_architecture_and_technical_design", version: 1, exit: "design_baseline" },
  9: { file: "phase_09_development_and_implementation", version: 2, exit: "implementation_report" },
  10: { file: "phase_10_quality_assurance_and_testing", version: 1, exit: "qa_completion_report" },
  11: { file: "phase_11_customer_uat_and_sign_off", version: 1, exit: "uat_signoff_record" },
  12: { file: "phase_12_production_go_live" }, 13: { file: "phase_13_project_closure" },
};

export function WorkflowConfiguration() {
  const world = useDemo((s) => s.world);
  return (
    <div className="space-y-5">
      <PageHeader title="Workflow Configuration" crumbs={[{ label: "Administration" }]}
        description="Phase workflows, approval gates and the policies the workflow engine enforces. They are versioned files under config/, changed through code review; the demo shows them read-only." />
      <Panel title="Phase workflows" subtitle="config/workflows/; each phase uses the standard phase and task lifecycles" icon={Workflow} flush>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-line text-left text-2xs tracking-wide text-fg-subtle uppercase"><th className="px-4 py-2">Phase</th><th className="px-3 py-2">Primary agent</th><th className="px-3 py-2">Exit approval</th><th className="px-3 py-2">Approved by</th><th className="px-3 py-2">File</th></tr></thead>
            <tbody>
              {PHASES.map((ph) => {
                const f = PHASE_FILES[ph.number]!;
                const matrix = APPROVAL_MATRIX.find((m) => m.type === f.exit);
                return (
                  <tr key={ph.number} className="border-b border-line last:border-0 align-top">
                    <td className="px-4 py-2.5"><span className="font-medium">{ph.number}. {ph.name}</span>{!ph.mvp && <Tag tone="warning" className="ml-1.5">Preview</Tag>}</td>
                    <td className="px-3 py-2.5">{world.agentTypes.find((t) => t.key === ph.primaryAgent)?.name ?? ph.primaryAgent}</td>
                    <td className="px-3 py-2.5">{matrix ? matrix.title : <span className="text-fg-subtle">{ph.gate}</span>}</td>
                    <td className="px-3 py-2.5">{(matrix?.roles ?? ph.gateRoles).map((r) => ROLE_LABELS[r]).join(" or ")}</td>
                    <td className="px-3 py-2.5 font-mono text-2xs text-fg-muted">{f.file}.yaml{f.version ? ` · v${f.version}` : <span className="ml-1 font-sans text-fg-subtle">(scaffold)</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Approval policies" subtitle="config/policies/approval_matrix.yaml · independent review on every type" icon={Scale} flush>
          <ul className="divide-y divide-line">
            {APPROVAL_MATRIX.map((m) => (
              <li key={m.type} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1">{m.title}<span className="block font-mono text-2xs text-fg-subtle">{m.type}</span></span>
                <span className="flex flex-wrap gap-1">{m.roles.map((r) => <Tag key={r} tone="violet">{ROLE_LABELS[r]}</Tag>)}</span>
              </li>
            ))}
            <li className="px-4 py-2.5 text-[13px]">Decisions raised by agents: <Tag tone="violet">Owner</Tag> <Tag tone="violet">Project manager</Tag></li>
            <li className="px-4 py-2.5 text-[13px]">Change requests: scope (requirements) needs the owner and the customer approver; a design change needs the owner and a reviewer. Never approved by the person who raised it.</li>
          </ul>
        </Panel>
        <div className="space-y-5">
          <Panel title="Separation of duties" subtitle="config/policies/separation_of_duties.yaml, incident_rules.yaml" icon={Lock}>
            <ul className="list-disc space-y-1.5 pl-4 text-[13px]">{SEPARATION_OF_DUTIES.map((r) => <li key={r}>{r}</li>)}</ul>
          </Panel>
          <Panel title="Change sets" subtitle="config/policies/change_sets.yaml" icon={FileCode}>
            <ul className="list-disc space-y-1.5 pl-4 text-[13px]">{CHANGE_SET_RULES.map((r) => <li key={r}>{r}</li>)}</ul>
          </Panel>
          <Panel title="Retries and failures" subtitle="config/models.yaml, incident_rules.yaml" icon={ShieldCheck}>
            <ul className="list-disc space-y-1.5 pl-4 text-[13px]">
              <li>Model calls: 2 retries, 240 s timeout; agent tasks: at most 2 attempts.</li>
              <li>A failed run opens an incident by its error code (rate limited, provider unavailable, guardrail blocked, …); waiting states do not.</li>
              <li>A repeat failure on the same task is recorded on the open incident, not as a new one.</li>
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* Users and Permissions ------------------------------------------------------------------------------- */

export function UsersPermissions() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const setRole = useDemo((s) => s.setRole);
  const plays = (personId: string) => (Object.keys(ROLE_PEOPLE) as Role[]).find((r) => ROLE_PEOPLE[r] === personId);
  return (
    <div className="space-y-5">
      <PageHeader title="Users and Permissions" crumbs={[{ label: "Administration" }]}
        description="The people in this demo, their roles and what each role may do. Agents have their own service accounts and may author and propose, never approve or decide." />
      <Panel title={`${world.people.length} people`} icon={Users} flush>
        <DataTable
          rows={world.people}
          rowKey={(p) => p.id}
          columns={[
            { key: "name", header: "Name", sortValue: (p) => p.name, render: (p) => <span className="flex items-center gap-2"><Avatar name={p.name} size="sm" /><span><span className="block font-medium">{p.name}</span><span className="block text-2xs text-fg-subtle">{p.title}</span></span></span> },
            { key: "role", header: "Role", sortValue: (p) => p.role, render: (p) => <Tag tone="violet">{ROLE_LABELS[p.role]}</Tag> },
            { key: "org", header: "Organization", hideBelow: "md", render: (p) => (p.customerId ? byId(world.customers, p.customerId)?.name : "Agentra") },
            { key: "sign-in", header: "Sign-in", hideBelow: "lg", render: () => <span className="text-xs text-fg-muted">Single sign-on, MFA</span> },
            {
              key: "act", header: "Demo", align: "right", render: (p) => {
                const r = plays(p.id);
                if (!r) return <span className="text-2xs text-fg-subtle">Same role as {actorName(world, ROLE_PEOPLE[p.role])}</span>;
                return r === role ? <Tag tone="success" icon={UserRound}>Acting now</Tag> : <Button size="sm" onClick={() => setRole(r)}>Act as {p.name.split(" ")[0]}</Button>;
              },
            },
          ]}
        />
      </Panel>

      <Panel title="Role permissions" subtitle="config/policies/permissions.yaml; project roles apply within each project" icon={KeyRound} flush>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-line text-2xs tracking-wide text-fg-subtle uppercase">
                <th scope="col" className="px-4 py-2 text-left">Permission</th>
                {ROLES.map((r) => <th key={r} scope="col" className="px-3 py-2 text-center">{ROLE_LABELS[r]}</th>)}
                <th scope="col" className="px-3 py-2 text-center">Agents</th>
              </tr>
            </thead>
            <tbody>
              {PERMISSIONS.map((p) => (
                <tr key={p.key} className="border-b border-line">
                  <th scope="row" className="px-4 py-2 text-left font-normal">{p.label}<span className="block font-mono text-2xs text-fg-subtle">{p.key}</span></th>
                  {[...ROLES, "agent" as const].map((r) => (
                    <td key={r} className="px-3 py-2 text-center">
                      {ROLE_PERMISSIONS[r].includes(p.key) ? <CircleCheck className="mx-auto size-4 text-success" aria-label="Allowed" /> : <span className="text-fg-subtle" aria-label="Not allowed">–</span>}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <th scope="row" className="px-4 py-2 text-left font-normal">Approve or decide<span className="block text-2xs text-fg-subtle">by artifact type: see Workflow Configuration</span></th>
                {ROLES.map((r) => { const n = APPROVAL_MATRIX.filter((m) => m.roles.includes(r)).length; return <td key={r} className="px-3 py-2 text-center text-xs">{n} type{n === 1 ? "" : "s"}</td>; })}
                <td className="px-3 py-2 text-center"><Ban className="mx-auto size-4 text-danger" aria-label="Never" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
      <p className="text-2xs text-fg-subtle">Platform administration (creating projects, managing users, verifying the audit log) belongs to the founder account; in the demo that is the owner.</p>
    </div>
  );
}

/* System Settings ------------------------------------------------------------------------------------- */

const SECURITY = [
  ["Sign-in", "Microsoft Entra ID single sign-on; MFA required for every person"],
  ["Sessions", "Signed out after 8 hours, or 30 minutes idle"],
  ["Secrets", "In the secrets vault only; never in source, prompts, logs or documents"],
  ["Code execution", "Only in isolated sandbox VMs, never on the Agentra host"],
  ["Production tenants", "None connected in the MVP"],
  ["Audit log", "Append-only; every consequential action is recorded"],
  ["Data", "Synthetic data in this demo; customer data stays in the customer's tenant"],
] as const;

function auditCsv(entries: AuditEntry[], name: (id: string) => string): string {
  const cell = (s: string) => (/[",\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s);
  return ["When,Actor,Action,Target,Detail", ...entries.map((a) => [a.at, name(a.actor), a.action, a.target, a.detail ?? ""].map(cell).join(","))].join("\r\n");
}

export function SystemSettings() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const data = useDataService();
  const exportAction = useRuleAction();
  const [query, setQuery] = useState("");
  const [actor, setActor] = useState("all");
  const entries = world.audit.filter((a) => {
    const isPerson = world.people.some((p) => p.id === a.actor);
    const kind = a.actor === "system" ? "system" : isPerson ? "people" : "agents";
    return (actor === "all" || kind === actor) && `${a.action} ${a.target} ${a.detail ?? ""} ${actorName(world, a.actor)}`.toLowerCase().includes(query.toLowerCase().trim());
  });
  const download = () => {
    const blob = new Blob([auditCsv(entries, (id) => actorName(world, id))], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agentra-audit-${world.now.slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <PageHeader title="System Settings" crumbs={[{ label: "Administration" }]} description="Security settings, your notification preferences and the audit log." />
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Security" subtitle="Set by policy; shown read-only" icon={ShieldCheck}>
          <dl className="space-y-2.5">{SECURITY.map(([k, v]) => <div key={k} className="grid grid-cols-[130px_1fr] gap-3 text-[13px]"><dt className="text-fg-subtle">{k}</dt><dd>{v}</dd></div>)}</dl>
        </Panel>
        <Panel title="Notification preferences" subtitle={`For you, as ${ROLE_LABELS[role].toLowerCase()} (${actorName(world, ROLE_PEOPLE[role])}); delivery is simulated`} icon={Bell} flush>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="border-b border-line text-2xs tracking-wide text-fg-subtle uppercase"><th className="px-4 py-2 text-left">Event</th>{CHANNELS.map((c) => <th key={c.key} className="px-3 py-2 text-center">{c.label}</th>)}</tr></thead>
              <tbody>
                {NOTIFICATION_EVENTS.map((e) => (
                  <tr key={e.key} className="border-b border-line last:border-0">
                    <th scope="row" className="px-4 py-2 text-left font-normal">{e.label}</th>
                    {CHANNELS.map((c) => {
                      const key = `${e.key}.${c.key}`;
                      const on = world.settings.notifications[`${role}.${key}`] ?? false;
                      return (
                        <td key={c.key} className="px-3 py-2 text-center">
                          <input type="checkbox" checked={on} onChange={(ev) => data.setNotification(key, ev.target.checked)} aria-label={`${e.label}: ${c.label}`} className="size-4 accent-[var(--primary)]" />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Panel title="Audit log" subtitle={`${world.audit.length} entries, newest first; append-only`} icon={ScrollText} flush
        actions={<Button size="sm" icon={Download} onClick={() => exportAction.run(download, `Downloaded agentra-audit-${world.now.slice(0, 10)}.csv`)}>Export CSV</Button>}>
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
          <label className="flex h-8 w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] sm:w-72">
            <Search className="size-4 text-fg-subtle" aria-hidden />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search the audit log" aria-label="Search the audit log" className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-fg-subtle" />
          </label>
          <select value={actor} onChange={(e) => setActor(e.target.value)} aria-label="Actor" className="h-8 rounded-lg border border-line bg-surface px-2 text-[13px]">
            <option value="all">Everyone</option><option value="people">People</option><option value="agents">Agents</option><option value="system">Agentra (system)</option>
          </select>
          {exportAction.done && <span role="status" className="text-xs text-success">{exportAction.done}</span>}
          {exportAction.error && <span role="alert" className="text-xs text-danger">{exportAction.error}</span>}
          <span className="ml-auto text-xs text-fg-subtle">{entries.length} shown</span>
        </div>
        <DataTable<AuditEntry>
          rows={entries}
          rowKey={(a) => a.id}
          dense
          empty="No audit entries match"
          columns={[
            { key: "at", header: "When", sortValue: (a) => a.at, render: (a) => <span className="whitespace-nowrap text-xs text-fg-muted">{formatDateTime(a.at)}</span> },
            { key: "actor", header: "Actor", sortValue: (a) => actorName(world, a.actor), render: (a) => <span className="whitespace-nowrap">{actorName(world, a.actor)}</span> },
            { key: "action", header: "Action", sortValue: (a) => a.action, render: (a) => <span className="font-mono text-2xs">{a.action}</span> },
            { key: "target", header: "Target", render: (a) => a.target },
            { key: "detail", header: "Detail", hideBelow: "lg", render: (a) => <span className="text-xs text-fg-muted">{a.detail}</span> },
          ]}
        />
      </Panel>
    </div>
  );
}
