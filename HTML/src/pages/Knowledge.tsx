/* S11 Document and Knowledge Center: every project document with its versions, review status, owner, source agent,
   approval history and traceability, and a preview panel (?doc=<id>). Only approved versions are knowledge agents
   may ground their work on. */
import { useState } from "react";
import { BookOpen, Bot, CircleCheck, FileText, Fingerprint, GitCompareArrows, Link2, Search, UserRound } from "lucide-react";
import { Link, useSearchParams } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { Kpi } from "@/components/ui/Kpi";
import { Field, Panel } from "@/components/ui/Panel";
import { EmptyState } from "@/components/ui/States";
import { ARTIFACT_STATUS, DECISION_STATUS } from "@/components/ui/status";
import { phaseDef } from "@/data/lifecycle";
import { formatDateTime, relative } from "@/lib/format";
import { actorName, byId, latestVersion } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Artifact, ArtifactStatus, ArtifactType, World } from "@/types";

export const TYPE_LABELS: Record<ArtifactType, string> = {
  brd: "Business requirements (BRD)", sad: "Solution architecture", hld: "High-level design", lld: "Low-level design", tech_spec: "Technical specification",
  security_review: "Security review", backlog: "Implementation backlog", change_set: "Source code (change set)", test_plan: "Test plan", test_report: "Test report",
  uat_report: "UAT report", signoff: "Sign-off record", minutes: "Meeting minutes", report: "Project report", proposal: "Proposal",
};

function Select<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as T)} aria-label={label} className="h-9 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-fg">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

/** Documents that share a trace ID with this one (requirements, design items, work items, tests). */
function relatedByTrace(world: World, doc: Artifact): { artifact: Artifact; shared: string[] }[] {
  return world.artifacts
    .filter((a) => a.id !== doc.id)
    .map((a) => ({ artifact: a, shared: a.traces.filter((t) => doc.traces.includes(t)) }))
    .filter((r) => r.shared.length > 0);
}

function Preview({ world, doc }: { world: World; doc: Artifact }) {
  const latest = latestVersion(doc);
  const approved = [...doc.versions].reverse().find((v) => v.status === "approved");
  const approvals = world.decisions.filter((d) => d.artifactId === doc.id);
  const related = relatedByTrace(world, doc);
  const project = byId(world.projects, doc.projectId);
  return (
    <article aria-label={`${doc.title} preview`} className="space-y-5">
      <header>
        <div className="flex flex-wrap items-center gap-1.5"><Tag>{TYPE_LABELS[doc.type]}</Tag><StatusPill size="sm" meta={ARTIFACT_STATUS[latest.status]} />{approved && <Tag tone="success" icon={BookOpen}>Approved knowledge: v{approved.no}</Tag>}</div>
        <h2 className="mt-2 text-lg font-semibold">{doc.title} <span className="text-fg-subtle">v{latest.no}</span></h2>
        <p className="text-xs text-fg-subtle">{project?.name} · Phase {doc.phase}, {phaseDef(doc.phase).short}</p>
      </header>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Owner"><span className="inline-flex items-center gap-1.5"><Avatar name={actorName(world, doc.ownerId)} size="sm" />{actorName(world, doc.ownerId)}</span></Field>
        <Field label="Source agent">{doc.sourceAgentId ? <Link to={`/agents?agent=${doc.sourceAgentId}`} className="inline-flex items-center gap-1.5 hover:text-primary-strong"><Avatar name={actorName(world, doc.sourceAgentId)} agent size="sm" />{actorName(world, doc.sourceAgentId)}</Link> : "Written by people"}</Field>
        <Field label="Last change">{formatDateTime(latest.at)} ({relative(latest.at, world.now)})</Field>
      </dl>

      <section aria-label="Document preview" className="rounded-lg border border-line bg-surface-2/50 p-4">
        <p className="mb-2 text-2xs font-semibold tracking-wide text-fg-subtle uppercase">Preview · version {latest.no}</p>
        <p className="font-serif text-[15px] leading-relaxed">{doc.excerpt}</p>
        <p className="mt-3 text-2xs text-fg-subtle">The full document lives in the project's SharePoint library once approved (simulated). Agents read approved versions only.</p>
      </section>

      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-fg-muted uppercase"><GitCompareArrows className="size-3.5" aria-hidden />Versions</h3>
        <ol className="space-y-2">
          {[...doc.versions].reverse().map((v) => (
            <li key={v.no} className="rounded-lg border border-line p-3 text-[13px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">v{v.no}</span>
                <StatusPill size="sm" meta={ARTIFACT_STATUS[v.status]} />
                <span className="text-2xs text-fg-subtle">{formatDateTime(v.at)} · by {actorName(world, v.author)}{v.reviewedBy ? ` · reviewed by ${actorName(world, v.reviewedBy)}` : ""}</span>
              </div>
              <p className="mt-1 text-fg-muted">{v.summary}</p>
              <p className="mt-1 flex items-center gap-1 font-mono text-2xs text-fg-subtle"><Fingerprint className="size-3" aria-hidden />sha256 {v.sha256.slice(0, 24)}…</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-fg-muted uppercase"><CircleCheck className="size-3.5" aria-hidden />Approval history</h3>
        {approvals.length === 0 && !doc.versions.some((v) => v.reviewedBy) ? <p className="text-[13px] text-fg-muted">No approvals requested yet.</p> : (
          <ul className="space-y-1.5 text-[13px]">
            {doc.versions.filter((v) => v.reviewedBy).map((v) => (
              <li key={`r${v.no}`} className="flex items-center gap-2"><UserRound className="size-3.5 text-fg-subtle" aria-hidden />v{v.no}: {ARTIFACT_STATUS[v.status].label.toLowerCase()} by {actorName(world, v.reviewedBy!)}</li>
            ))}
            {approvals.map((d) => (
              <li key={d.id}><Link to={`/decisions?id=${d.id}`} className="flex flex-wrap items-center gap-2 hover:text-primary-strong">
                <Tag>{d.code}</Tag>{d.title}<StatusPill size="sm" meta={DECISION_STATUS[d.status]} />
                {d.outcome?.boundTo && <span className="font-mono text-2xs text-fg-subtle">bound to v{d.outcome.boundTo.version}</span>}
              </Link></li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-fg-muted uppercase"><Link2 className="size-3.5" aria-hidden />Traceability</h3>
        {doc.traces.length === 0 ? <p className="text-[13px] text-fg-muted">No trace references.</p> : (
          <>
            <div className="flex flex-wrap gap-1.5">{doc.traces.map((t) => <Tag key={t} tone="primary">{t}</Tag>)}</div>
            {related.length > 0 && (
              <ul className="mt-3 space-y-1.5" aria-label="Documents sharing these references">
                {related.map(({ artifact, shared }) => (
                  <li key={artifact.id}><Link to={`/knowledge?doc=${artifact.id}`} className="flex items-center gap-2 rounded-md border border-line px-2.5 py-1.5 text-xs hover:bg-surface-2">
                    <FileText className="size-3.5 text-fg-subtle" aria-hidden /><span className="min-w-0 flex-1 truncate">{artifact.title} <span className="text-fg-subtle">· {byId(world.projects, artifact.projectId)?.code}</span></span>
                    <span className="text-2xs text-fg-subtle">{shared.join(", ")}</span>
                  </Link></li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </article>
  );
}

export function KnowledgeBase() {
  const world = useDemo((s) => s.world);
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<ArtifactType | "all">("all");
  const [project, setProject] = useState("all");
  const [status, setStatus] = useState<ArtifactStatus | "all">("all");
  const docs = world.artifacts
    .filter((a) => (type === "all" || a.type === type) && (project === "all" || a.projectId === project) && (status === "all" || latestVersion(a).status === status))
    .filter((a) => `${a.title} ${TYPE_LABELS[a.type]} ${a.excerpt} ${a.traces.join(" ")}`.toLowerCase().includes(query.toLowerCase().trim()))
    .sort((a, b) => Date.parse(latestVersion(b).at) - Date.parse(latestVersion(a).at));
  const selected = byId(world.artifacts, params.get("doc") ?? undefined) ?? docs[0];
  const open = (id: string) => setParams((p) => { p.set("doc", id); return p; });
  const types = [...new Set(world.artifacts.map((a) => a.type))];
  const count = (s: ArtifactStatus) => world.artifacts.filter((a) => latestVersion(a).status === s).length;

  return (
    <div className="space-y-5">
      <PageHeader title="Knowledge Base" crumbs={[{ label: "Intelligence" }]}
        description="Every project document with its versions, review status, owner, source agent, approval history and traceability. Agents ground their work only on approved versions." />
      <section aria-label="Document figures" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Documents" value={world.artifacts.length} icon={FileText} hint={`${world.artifacts.reduce((s, a) => s + a.versions.length, 0)} versions`} />
        <Kpi label="Approved" value={count("approved")} icon={CircleCheck} tone="success" hint="usable as knowledge" onClick={() => setStatus("approved")} pressed={status === "approved"} />
        <Kpi label="In review" value={count("in_review")} icon={UserRound} tone="violet" hint="waiting for a person" onClick={() => setStatus("in_review")} pressed={status === "in_review"} />
        <Kpi label="Drafted by agents" value={world.artifacts.filter((a) => a.sourceAgentId).length} icon={Bot} tone="cyan" hint="reviewed by people" />
      </section>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[13px] sm:w-72">
          <Search className="size-4 text-fg-subtle" aria-hidden />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search documents and trace IDs" aria-label="Search documents" className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-fg-subtle" />
        </label>
        <Select label="Type" value={type} onChange={setType} options={[["all", "All types"], ...types.map((t) => [t, TYPE_LABELS[t]] as [ArtifactType, string])]} />
        <Select label="Project" value={project} onChange={setProject} options={[["all", "All projects"], ...world.projects.map((p) => [p.id, p.name] as [string, string])]} />
        <Select label="Status" value={status} onChange={setStatus} options={[["all", "Any status"], ...(Object.keys(ARTIFACT_STATUS) as ArtifactStatus[]).map((s) => [s, ARTIFACT_STATUS[s].label] as [ArtifactStatus, string])]} />
        <span className="ml-auto text-xs text-fg-subtle">{docs.length} shown</span>
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <Panel title="Documents" icon={FileText} flush>
          {docs.length === 0 ? <EmptyState icon={FileText} title="No documents match" hint="Change the filters or the search." /> : (
            <ul aria-label="Documents" className="divide-y divide-line">
              {docs.map((d) => {
                const v = latestVersion(d);
                return (
                  <li key={d.id}>
                    <button type="button" onClick={() => open(d.id)} aria-pressed={selected?.id === d.id}
                      className={cn("flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-surface-2", selected?.id === d.id && "bg-surface-2")}>
                      <FileText className="mt-0.5 size-4 shrink-0 text-fg-subtle" aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] font-medium">{d.title} <span className="font-normal text-fg-subtle">v{v.no}</span></span>
                        <span className="block text-2xs text-fg-subtle">{TYPE_LABELS[d.type]} · {byId(world.projects, d.projectId)?.code} · {d.sourceAgentId ? actorName(world, d.sourceAgentId) : "people"} · {relative(v.at, world.now)}</span>
                      </span>
                      <StatusPill size="sm" meta={ARTIFACT_STATUS[v.status]} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
        <Panel title="Preview" icon={BookOpen} className="xl:sticky xl:top-4 xl:self-start">
          {selected ? <Preview world={world} doc={selected} /> : <EmptyState title="Select a document" />}
        </Panel>
      </div>
    </div>
  );
}
