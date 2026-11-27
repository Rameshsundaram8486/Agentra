/* The presenter guide (#/guide): a 15-minute story through the demo with setup, steps, talking points, the rules each
   step shows, likely questions and how to recover. Each step opens its screen and, where it matters, sets the role. */
import { ArrowRight, CircleHelp, ListChecks, Presentation, ShieldCheck, Timer, UserRound, Wrench } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Panel";
import { GUIDE_QUESTIONS, GUIDE_RECOVERY, GUIDE_SETUP, GUIDE_STEPS, type GuideStep } from "@/data/presenterGuide";
import { ROLE_LABELS } from "@/store/actions";
import { useDemo } from "@/store/useDemo";

function Step({ step, n }: { step: GuideStep; n: number }) {
  const setRole = useDemo((s) => s.setRole);
  const navigate = useNavigate();
  const open = () => {
    if (step.role) setRole(step.role);
    navigate(step.link);
  };
  return (
    <li aria-label={`Step ${n}: ${step.title}`} className="rounded-[var(--radius-panel)] border border-line bg-surface p-4 shadow-panel">
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary-strong">{n}</span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold">{step.title}</h2>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-2xs text-fg-subtle">
            <span className="inline-flex items-center gap-1"><Timer className="size-3" aria-hidden />{step.minutes} min</span>
            {step.role && <span className="inline-flex items-center gap-1"><UserRound className="size-3" aria-hidden />as {ROLE_LABELS[step.role].toLowerCase()}</span>}
            <span className="font-mono">#{step.link}</span>
          </p>
        </div>
        <Button size="sm" variant="primary" icon={ArrowRight} onClick={open}>{step.role ? `Open as ${ROLE_LABELS[step.role].toLowerCase()}` : "Open"}</Button>
      </div>
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="text-2xs font-semibold tracking-wide text-fg-subtle uppercase">Do</h3>
          <ol className="mt-1 list-decimal space-y-1 pl-4 text-[13px]">{step.doThis.map((d) => <li key={d}>{d}</li>)}</ol>
        </div>
        <div>
          <h3 className="text-2xs font-semibold tracking-wide text-fg-subtle uppercase">Say</h3>
          <p className="mt-1 text-[13px] text-fg-muted">"{step.say}"</p>
          {step.rule && <p className="mt-2 flex items-start gap-1.5 text-xs"><ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden /><span><span className="text-fg-subtle">Rule shown: </span>{step.rule}</span></p>}
        </div>
      </div>
    </li>
  );
}

export function Guide() {
  const total = GUIDE_STEPS.reduce((s, step) => s + step.minutes, 0);
  return (
    <div className="space-y-5">
      <PageHeader title="Presenter guide" crumbs={[{ label: "Demo" }]}
        description={`A ${total}-minute story through the Command Center for executive, customer and investor demonstrations. Each step opens its screen and sets the role to act as.`}
        meta={<Tag tone="primary" icon={Presentation}>{GUIDE_STEPS.length} steps · {total} min</Tag>} />

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Before you start" icon={ListChecks}>
          <ol className="list-decimal space-y-1.5 pl-4 text-[13px]">{GUIDE_SETUP.map((s) => <li key={s}>{s}</li>)}</ol>
        </Panel>
        <Panel title="If something goes wrong" icon={Wrench}>
          <ul className="list-disc space-y-1.5 pl-4 text-[13px]">{GUIDE_RECOVERY.map((s) => <li key={s}>{s}</li>)}</ul>
        </Panel>
      </div>

      <ol aria-label="Story" className="space-y-4">
        {GUIDE_STEPS.map((step, i) => <Step key={step.id} step={step} n={i + 1} />)}
      </ol>

      <Panel title="Questions you may be asked" icon={CircleHelp}>
        <dl className="space-y-3">
          {GUIDE_QUESTIONS.map(({ q, a }) => (
            <div key={q}><dt className="text-[13px] font-medium">{q}</dt><dd className="mt-0.5 text-[13px] text-fg-muted">{a}</dd></div>
          ))}
        </dl>
      </Panel>
      <p className="text-2xs text-fg-subtle">The design system and component gallery is at <Link to="/design-system" className="text-primary-strong hover:underline">#/design-system</Link>.</p>
    </div>
  );
}
