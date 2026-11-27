/* The Project Owner Intelligence Briefing: a summary on the Command Center and the full briefing in a drawer.
   Findings are facts from records; recommended actions and priorities are the agent's proposals, labelled as such. */
import { useState } from "react";
import { ArrowRight, BrainCircuit, Database, Radar } from "lucide-react";
import { Link } from "react-router";
import { Avatar } from "@/components/ui/Avatar";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Drawer } from "@/components/ui/Overlays";
import { PRIORITY, RISK_STATUS, TONE_DOT, TONE_TEXT, type Tone } from "@/components/ui/status";
import { relative } from "@/lib/format";
import { ROLE_LABELS } from "@/store/actions";
import { briefing, type Briefing, type BriefingStatus, type Finding } from "@/store/briefing";
import { byId, riskLevel, riskScore } from "@/store/selectors";
import type { World } from "@/types";

export const STATUS: Record<BriefingStatus, { label: string; tone: Tone }> = {
  healthy: { label: "Healthy", tone: "success" },
  watch: { label: "Needs watching", tone: "warning" },
  critical: { label: "Needs action", tone: "danger" },
};

const FINDING_TONE: Record<Finding["severity"], Tone> = { critical: "danger", warning: "warning", info: "primary" };

export function ScoreRing({ score, status }: { score: number; status: BriefingStatus }) {
  const tone = STATUS[status].tone;
  const circumference = 2 * Math.PI * 30;
  return (
    <div className="relative size-20 shrink-0" role="img" aria-label={`Company health score ${score} of 100: ${STATUS[status].label}`}>
      <svg viewBox="0 0 72 72" className="size-20 -rotate-90">
        <circle cx="36" cy="36" r="30" fill="none" stroke="var(--surface-3)" strokeWidth="7" />
        <circle cx="36" cy="36" r="30" fill="none" stroke={`var(--${tone === "danger" ? "danger" : tone})`} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)} className="transition-[stroke-dashoffset] duration-700" />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div><div className="text-xl leading-none font-semibold tabular">{score}</div><div className="text-[10px] text-fg-subtle">of 100</div></div>
      </div>
    </div>
  );
}

export function SourceTag({ kind }: { kind: "record" | "ai" }) {
  return kind === "record" ? (
    <Tag tone="neutral" icon={Database} title="Read from recorded workflow data">From records</Tag>
  ) : (
    <Tag tone="violet" icon={BrainCircuit} title="The Project Owner Agent's proposal; people decide">AI recommendation</Tag>
  );
}

export function FindingRow({ finding }: { finding: Finding }) {
  return (
    <li>
      <Link to={finding.link} className="group flex items-start gap-2 rounded-md px-1.5 py-1 hover:bg-surface-2">
        <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", TONE_DOT[FINDING_TONE[finding.severity]])} aria-hidden />
        <span className="text-[13px] text-fg">{finding.text}</span>
      </Link>
    </li>
  );
}

function FullBriefing({ world, brief }: { world: World; brief: Briefing }) {
  const owner = world.agents.find((a) => a.typeKey === "project_owner");
  return (
    <div className="space-y-6">
      <section className="flex items-center gap-4">
        <ScoreRing score={brief.score} status={brief.status} />
        <div>
          <p className={cn("text-sm font-semibold", TONE_TEXT[STATUS[brief.status].tone])}>{STATUS[brief.status].label}</p>
          <p className="text-[13px] text-fg">{brief.headline}</p>
          {owner && <p className="mt-1 text-2xs text-fg-subtle">Prepared by the {owner.name} at {new Date(world.now).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Dubai" })} (simulated time) from {world.projects.length} projects, {world.tasks.length} tasks and {world.decisions.length} decisions.</p>}
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Important findings</h3><SourceTag kind="record" /></div>
        <ul className="space-y-0.5">{brief.findings.map((f) => <FindingRow key={f.text} finding={f} />)}</ul>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Risks detected</h3><SourceTag kind="record" /></div>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {brief.risks.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
              <Tag tone={riskLevel(r) === "critical" ? "danger" : riskLevel(r) === "high" ? "warning" : "primary"}>{r.code} · score {riskScore(r)}</Tag>
              <span className="min-w-0 flex-1 text-[13px]">{r.title}<span className="block text-2xs text-fg-subtle">{byId(world.projects, r.projectId)?.name} · Mitigation: {r.mitigation}</span></span>
              <StatusPill size="sm" meta={RISK_STATUS[r.status]} />
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Recommended actions</h3><SourceTag kind="ai" /></div>
        <ul className="space-y-1.5">
          {brief.actions.map((a) => (
            <li key={a.text}>
              <Link to={a.link} className="block rounded-lg border border-line px-3 py-2 hover:border-line-strong hover:bg-surface-2">
                <span className="block text-[13px]">{a.text}</span>
                <span className="block text-2xs text-fg-subtle">Based on {a.basis} · for the {ROLE_LABELS[a.owner].toLowerCase()}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold">Pending escalations</h3>
        {brief.escalations.length === 0 ? <p className="text-[13px] text-fg-muted">None.</p> : (
          <ul className="space-y-1.5">
            {brief.escalations.map((d) => (
              <li key={d.id}>
                <Link to={`/decisions?id=${d.id}`} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 hover:bg-surface-2">
                  <StatusPill size="sm" meta={PRIORITY[d.priority]} />
                  <span className="min-w-0 flex-1 text-[13px]">{d.code} {d.title}</span>
                  <span className="text-2xs text-fg-subtle">due {relative(d.deadline, world.now)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Recommended priorities</h3><SourceTag kind="ai" /></div>
        <ol className="space-y-1">
          {brief.priorities.map((p) => (
            <li key={p.rank}>
              <Link to={p.link} className="flex items-center gap-2.5 rounded-md px-1.5 py-1 text-[13px] hover:bg-surface-2">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-surface-3 text-2xs font-semibold tabular">{p.rank}</span>
                {p.text}
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <p className="rounded-lg bg-surface-2 px-3 py-2 text-2xs text-fg-subtle">
        Findings and risks are read from recorded workflow data. Recommended actions and priorities are the Project Owner Agent's proposals;
        root causes from incidents are hypotheses until verified. People decide.
      </p>
    </div>
  );
}

export function OwnerBriefing({ world }: { world: World }) {
  const [open, setOpen] = useState(false);
  const brief = briefing(world);
  const owner = world.agents.find((a) => a.typeKey === "project_owner");
  return (
    <section aria-labelledby="briefing-title" className="relative overflow-hidden rounded-[var(--radius-panel)] border border-primary/25 bg-surface shadow-panel">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-primary-soft to-transparent" />
      <header className="relative flex flex-wrap items-center justify-between gap-3 px-4 pt-3.5">
        <div className="flex items-center gap-2.5">
          {owner ? <Avatar name={owner.name} agent /> : <Radar className="size-5" />}
          <div>
            <h2 id="briefing-title" className="text-sm font-semibold">Project Owner Intelligence Briefing</h2>
            <p className="text-2xs text-fg-subtle">{owner?.name} · updated {relative(world.activity[0]?.at ?? world.now, world.now)} · simulated</p>
          </div>
        </div>
        <Button size="sm" variant="primary" icon={ArrowRight} onClick={() => setOpen(true)}>Open full briefing</Button>
      </header>
      <div className="relative grid gap-5 p-4 md:grid-cols-2 2xl:grid-cols-[auto_1fr_1fr]">
        <div className="flex items-center gap-3 md:col-span-2 2xl:col-span-1 2xl:flex-col 2xl:items-start">
          <ScoreRing score={brief.score} status={brief.status} />
          <div className="2xl:max-w-56">
            <p className={cn("text-[13px] font-semibold", TONE_TEXT[STATUS[brief.status].tone])}>{STATUS[brief.status].label}</p>
            <p className="text-xs text-fg-muted">{brief.headline}</p>
          </div>
        </div>
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center justify-between gap-2"><h3 className="text-xs font-semibold text-fg-muted">Findings</h3><SourceTag kind="record" /></div>
          <ul className="space-y-0.5">{brief.findings.slice(0, 4).map((f) => <FindingRow key={f.text} finding={f} />)}</ul>
          {brief.findings.length > 4 && <button type="button" onClick={() => setOpen(true)} className="mt-1 px-1.5 text-xs text-primary-strong hover:underline">{brief.findings.length - 4} more findings</button>}
        </div>
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center justify-between gap-2"><h3 className="text-xs font-semibold text-fg-muted">Recommended priorities</h3><SourceTag kind="ai" /></div>
          <ol className="space-y-0.5">
            {brief.priorities.slice(0, 4).map((p) => (
              <li key={p.rank}>
                <Link to={p.link} className="flex items-start gap-2 rounded-md px-1.5 py-1 text-[13px] hover:bg-surface-2">
                  <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full bg-surface-3 text-[10px] font-semibold tabular">{p.rank}</span>
                  {p.text}
                </Link>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <Drawer open={open} onOpenChange={setOpen} title="Project Owner Intelligence Briefing" description="Company health, findings, risks, recommendations, escalations and priorities" width="w-[min(640px,100vw)]">
        <FullBriefing world={world} brief={brief} />
      </Drawer>
    </section>
  );
}
