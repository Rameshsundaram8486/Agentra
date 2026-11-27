/* S12 Integrations and the Model Gateway. Connections and usage are simulated: no credential, key or real tenant
   appears anywhere, and "test" and "sync" only record that they were asked for. The gateway shows the Claude API as
   the one active provider; Ollama and a cloud GPU endpoint are planned. */
import { Activity, CircleCheck, CircleDashed, CircleX, Cpu, Gauge, KeyRound, Plug, RefreshCw, Route, ShieldCheck, TriangleExclamationPoint, Zap } from "lucide-react";
import { useRuleAction } from "@/components/agents/useRuleAction";
import { BarList, LatencyChart } from "@/components/charts/Charts";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { Kpi } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { Progress } from "@/components/ui/States";
import type { StatusMeta } from "@/components/ui/status";
import { GATEWAY, MAX_TOKENS, PROVIDERS } from "@/data/seed/platform";
import { formatDateTime, number, relative, usd } from "@/lib/format";
import { useDataService } from "@/services/dataService";
import { ROLE_LABELS } from "@/store/actions";
import { actorName } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { AgentType, Integration, IntegrationStatus, World } from "@/types";

export const INTEGRATION_STATUS: Record<IntegrationStatus, StatusMeta> = {
  connected: { label: "Connected", tone: "success", icon: CircleCheck },
  warning: { label: "Needs attention", tone: "warning", icon: TriangleExclamationPoint },
  not_connected: { label: "Not connected", tone: "neutral", icon: CircleX },
  planned: { label: "Planned", tone: "neutral", icon: CircleDashed },
};

function IntegrationCard({ world, integration }: { world: World; integration: Integration }) {
  const data = useDataService();
  const action = useRuleAction();
  const live = integration.status === "connected" || integration.status === "warning";
  return (
    <article aria-label={integration.name} className="flex flex-col rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-medium">{integration.name}</h3>
          <p className="mt-0.5 text-xs text-fg-muted">{integration.purpose}</p>
        </div>
        <StatusPill size="sm" meta={INTEGRATION_STATUS[integration.status]} />
      </div>
      <dl className="mt-3 grid gap-1.5 text-xs">
        <div className="flex gap-1.5"><dt className="flex shrink-0 items-center gap-1 text-fg-subtle"><KeyRound className="size-3" aria-hidden />Auth</dt><dd>{integration.auth}</dd></div>
        <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Auth status</dt><dd className={integration.status === "warning" ? "text-warning" : ""}>{integration.authStatus}</dd></div>
        {integration.scopes.length > 0 && <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Scopes</dt><dd className="flex flex-wrap gap-1">{integration.scopes.map((s) => <Tag key={s}>{s}</Tag>)}</dd></div>}
        {integration.config.map(([label, value]) => <div key={label} className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">{label}</dt><dd>{value}</dd></div>)}
        {integration.lastSyncAt && <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Last sync</dt><dd>{formatDateTime(integration.lastSyncAt)} ({relative(integration.lastSyncAt, world.now)})</dd></div>}
        {integration.lastCheckAt && <div className="flex gap-1.5"><dt className="shrink-0 text-fg-subtle">Last tested</dt><dd>{relative(integration.lastCheckAt, world.now)}</dd></div>}
      </dl>
      {integration.note && <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-xs text-fg-muted">{integration.note}</p>}
      {action.error && <p role="alert" className="mt-3 text-xs text-danger">{action.error}</p>}
      {action.done && <p role="status" className="mt-3 text-xs text-success">{action.done}</p>}
      {live && (
        <div className="mt-auto flex justify-end gap-2 pt-4">
          {integration.syncs && <Button size="sm" icon={RefreshCw} onClick={() => action.run(() => data.integrationCommand(integration.id, "sync"), "Synced (simulated).")}>Sync now</Button>}
          <Button size="sm" icon={Zap} onClick={() => action.run(() => data.integrationCommand(integration.id, "check"), integration.status === "warning" ? `Connected, with a warning: ${integration.authStatus}.` : "Connected (simulated test).")}>Test connection</Button>
        </div>
      )}
    </article>
  );
}

export function Integrations() {
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const groups: Integration["group"][] = ["Microsoft 365", "Engineering", "Model providers"];
  const count = (s: IntegrationStatus) => world.integrations.filter((i) => i.status === s).length;
  return (
    <div className="space-y-5">
      <PageHeader title="Integrations" crumbs={[{ label: "Administration" }]}
        description="The systems Agentra connects to, with connection, authentication and sync status. Secrets live in the secrets vault and are never shown, logged or sent to a model."
        meta={<Tag tone="warning">Simulated connections</Tag>} />
      <section aria-label="Integration summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Connected" value={count("connected")} icon={CircleCheck} tone="success" />
        <Kpi label="Need attention" value={count("warning")} icon={TriangleExclamationPoint} tone="warning" hint="e.g. a certificate expiring" />
        <Kpi label="Not connected" value={count("not_connected")} icon={CircleX} tone="neutral" />
        <Kpi label="Planned" value={count("planned")} icon={CircleDashed} tone="neutral" hint="after the MVP" />
      </section>
      <p className="text-xs text-fg-subtle">Acting as {ROLE_LABELS[role].toLowerCase()}. Only the owner tests connections or starts a sync.</p>
      {groups.map((group) => (
        <section key={group} aria-label={group}>
          <h2 className="mb-3 text-sm font-semibold">{group}</h2>
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">{world.integrations.filter((i) => i.group === group).map((i) => <IntegrationCard key={i.id} world={world} integration={i} />)}</div>
        </section>
      ))}
    </div>
  );
}

/* Model Gateway --------------------------------------------------------------------------------------- */

export function gatewayUsage(world: World) {
  const runs = world.executions;
  const tokensIn = runs.reduce((s, e) => s + e.tokensIn, 0);
  const tokensOut = runs.reduce((s, e) => s + e.tokensOut, 0);
  const recordedCost = Math.round(runs.reduce((s, e) => s + e.costUsd, 0) * 100) / 100;
  const requests = runs.reduce((s, e) => s + e.attempt, 0);
  const failed = runs.filter((e) => e.status === "failed").length;
  const monthToDate = Math.round((GATEWAY.monthToDateUsd + recordedCost) * 100) / 100;
  return { tokensIn, tokensOut, recordedCost, requests, failed, monthToDate, capUsed: Math.round((monthToDate / GATEWAY.monthlyCapUsd) * 100) };
}

export function ModelGateway() {
  const world = useDemo((s) => s.world);
  const u = gatewayUsage(world);
  const p95 = Math.max(...GATEWAY.latency.map(([, , p]) => p));
  const byAgent = world.agents
    .map((a) => ({ agent: a, tokens: world.executions.filter((e) => e.agentId === a.id).reduce((s, e) => s + e.tokensIn + e.tokensOut, 0) }))
    .filter((r) => r.tokens > 0)
    .sort((a, b) => b.tokens - a.tokens);
  return (
    <div className="space-y-5">
      <PageHeader title="Model Gateway" crumbs={[{ label: "Administration" }]}
        description="Every model call goes through the gateway: routing, effort, token limits, retries, the monthly cap and usage. Nothing else talks to a model provider."
        meta={<Tag tone="warning">Simulated usage</Tag>} />
      <section aria-label="Gateway figures" className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <Kpi label="Endpoint" value="Operational" icon={Activity} tone="success" hint="api.anthropic.com (simulated)" />
        <Kpi label="Requests, 24 h" value={GATEWAY.requests24h} icon={Route} hint={`${u.requests} by the runs in this demo`} />
        <Kpi label="Tokens, demo runs" value={number(u.tokensIn + u.tokensOut)} icon={Cpu} tone="cyan" hint={`${number(u.tokensIn)} in · ${number(u.tokensOut)} out`} />
        <Kpi label="Latency p95" value={`${p95} s`} icon={Gauge} tone="violet" hint="time to first token, 24 h" />
        <Kpi label="Request failures" value={GATEWAY.failures.length} icon={TriangleExclamationPoint} tone="warning" hint={`${GATEWAY.failures.filter((f) => f.retried).length} recovered on retry`} />
        <Kpi label="Month to date" value={usd(u.monthToDate)} icon={ShieldCheck} tone={u.capUsed > 80 ? "danger" : "primary"} hint={`${u.capUsed}% of the USD ${GATEWAY.monthlyCapUsd} cap`} />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel title="Providers and models" icon={Cpu} flush>
          <ul className="divide-y divide-line">
            {PROVIDERS.map((p) => (
              <li key={p.id} className="flex items-start gap-3 px-4 py-3">
                <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium">{p.name}</span><span className="block text-xs text-fg-muted">{p.models.join(" · ")}</span></span>
                <StatusPill size="sm" meta={p.status === "Active" ? INTEGRATION_STATUS.connected : INTEGRATION_STATUS.planned} />
              </li>
            ))}
          </ul>
          <div className="border-t border-line px-4 py-3 text-xs text-fg-muted">
            <p className="flex items-center gap-1.5"><KeyRound className="size-3.5" aria-hidden />API key: stored in the secrets vault. It is never displayed, logged, or placed in a prompt.</p>
          </div>
        </Panel>
        <Panel title="Monthly cap" subtitle="config/models.yaml · budget.monthly_usd" icon={ShieldCheck}>
          <p className="flex items-baseline justify-between text-sm"><span className="text-2xl font-semibold tabular">{usd(u.monthToDate)}</span><span className="text-fg-muted">of {usd(GATEWAY.monthlyCapUsd)}</span></p>
          <Progress value={u.capUsed} tone={u.capUsed > 80 ? "danger" : "primary"} label="Monthly cap used" className="mt-2" />
          <p className="mt-3 text-xs text-fg-muted">A new call is refused when this month's spend plus the call's worst-case cost would exceed the cap. Calls started but not settled keep counting at their worst case.</p>
          <p className="mt-2 text-2xs text-fg-subtle">Includes {usd(u.recordedCost)} for the {world.executions.length} runs recorded in this demo.</p>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Latency" subtitle="Time to first token, p50 and p95, last 24 h (simulated)" icon={Gauge}><LatencyChart data={GATEWAY.latency} /></Panel>
        <Panel title="Token consumption" subtitle="Runs recorded in this demo, by agent" icon={Cpu}>
          <BarList label="Tokens by agent" items={byAgent.slice(0, 8).map((r) => ({ key: r.agent.id, label: r.agent.name, value: r.tokens, tone: "cyan" as const, to: `/agents?agent=${r.agent.id}` }))} />
        </Panel>
      </div>

      <Panel title="Routing" subtitle="config/models.yaml: the model, effort and token limit for each agent" icon={Route} flush>
        <DataTable<AgentType>
          rows={world.agentTypes}
          rowKey={(t) => t.key}
          dense
          columns={[
            { key: "agent", header: "Agent", sortValue: (t) => t.name, render: (t) => <span className="flex items-center gap-2 whitespace-nowrap"><Avatar name={t.name} agent size="sm" />{t.name}</span> },
            { key: "model", header: "Model", render: (t) => <span className="font-mono text-xs">{t.model}</span> },
            { key: "effort", header: "Effort", sortValue: (t) => t.effort, render: (t) => <Tag tone={t.effort === "xhigh" || t.effort === "high" ? "violet" : "neutral"}>{t.effort}</Tag> },
            { key: "tokens", header: "Max tokens", align: "right", hideBelow: "md", render: (t) => number(MAX_TOKENS[t.key] ?? GATEWAY.defaults.maxTokens) },
            { key: "retries", header: "Retries", align: "right", hideBelow: "lg", render: () => GATEWAY.defaults.maxRetries },
            { key: "scope", header: "Scope", hideBelow: "lg", render: (t) => (t.inMvp ? <Tag tone="primary">MVP</Tag> : <Tag tone="warning">Preview</Tag>) },
          ]}
        />
        <p className="border-t border-line px-4 py-2.5 text-2xs text-fg-subtle">Defaults: {GATEWAY.defaults.model}, effort {GATEWAY.defaults.effort}, {number(GATEWAY.defaults.maxTokens)} tokens, {GATEWAY.defaults.timeoutSeconds} s timeout, {GATEWAY.defaults.maxRetries} retries; on a policy refusal the API re-runs on Anthropic's recommended fallback model and the run records which model answered.</p>
      </Panel>

      <Panel title="Request failures" subtitle="By the gateway's error codes; each code's incident rule is in config/policies/incident_rules.yaml" icon={TriangleExclamationPoint} flush>
        <ul className="divide-y divide-line">
          {GATEWAY.failures.map((f) => (
            <li key={f.at} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-[13px]">
              <Tag tone={f.retried ? "neutral" : "warning"} className="font-mono">{f.code}</Tag>
              <span className="min-w-0 flex-1">{f.detail}<span className="block text-2xs text-fg-subtle">{actorName(world, f.agent)} · {relative(f.at, world.now)}</span></span>
              <StatusPill size="sm" meta={f.retried ? { label: "Recovered", tone: "success", icon: CircleCheck } : { label: "Blocked by guardrails", tone: "warning", icon: ShieldCheck }} />
            </li>
          ))}
        </ul>
      </Panel>
      <p className="flex items-center gap-1.5 text-2xs text-fg-subtle"><Plug className="size-3" aria-hidden />Agent output is checked by the guardrails in code (schema, grounding, forbidden claims, secrets) before anything is saved.</p>
    </div>
  );
}
