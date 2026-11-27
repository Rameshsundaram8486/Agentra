/* The 13-phase lifecycle as an interactive rail. For one project each phase shows its state; for the portfolio, how
   many projects are in it. Between phases sits the approval gate that must pass before the next phase starts. */
import { Ban, CircleCheck, CircleDot, LoaderCircle, Lock, UserCheck } from "lucide-react";
import { Tag } from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { PHASE_STATE, TONE_SOFT, TONE_TEXT, type Tone } from "@/components/ui/status";
import { PHASES } from "@/data/lifecycle";
import { currentPhase, isOpenDecision } from "@/store/selectors";
import type { PhaseState, Project, World } from "@/types";

export type GateState = "passed" | "waiting" | "blocked" | "ahead";

const GATE: Record<GateState, { label: string; tone: Tone; icon: typeof Lock }> = {
  passed: { label: "Gate passed", tone: "success", icon: CircleCheck },
  waiting: { label: "Waiting for people", tone: "violet", icon: UserCheck },
  blocked: { label: "Blocked", tone: "warning", icon: Ban },
  ahead: { label: "Gate ahead", tone: "neutral", icon: Lock },
};

const STATE_ICON: Record<PhaseState, typeof Lock> = { completed: CircleCheck, active: LoaderCircle, awaiting_approval: UserCheck, blocked: Ban, upcoming: CircleDot };

/** A phase's state across the portfolio: the most urgent state of any project in it. */
export function portfolioPhase(world: World, phase: number): { state: PhaseState; projects: Project[] } {
  const here = world.projects.filter((p) => p.status !== "completed" && currentPhase(p).phase === phase);
  const states = here.map((p) => p.phases[phase - 1]!.state);
  const state: PhaseState = states.includes("blocked") ? "blocked" : states.includes("awaiting_approval") ? "awaiting_approval" : states.includes("active") ? "active" : "upcoming";
  return { state, projects: here };
}

export function gateState(world: World, phase: number, project?: Project): GateState {
  if (project) {
    const p = project.phases[phase - 1]!;
    if (p.state === "completed") return "passed";
    if (p.state === "blocked") return "blocked";
    const waiting = world.decisions.some((d) => isOpenDecision(d) && d.projectId === project.id && d.phase === phase);
    return p.state === "awaiting_approval" || (p.state === "active" && waiting) ? "waiting" : "ahead";
  }
  const { state } = portfolioPhase(world, phase);
  if (state === "blocked") return "blocked";
  return world.decisions.some((d) => isOpenDecision(d) && d.phase === phase) ? "waiting" : "ahead";
}

const BANDS = [
  { label: "Pre-sales", from: 1, to: 5, mvp: false },
  { label: "Kickoff", from: 6, to: 6, mvp: false },
  { label: "MVP delivery", from: 7, to: 11, mvp: true },
  { label: "Release and closure", from: 12, to: 13, mvp: false },
];

export function LifecycleRail({ world, project, selected, onSelect }: { world: World; project?: Project; selected: number; onSelect: (phase: number) => void }) {
  return (
    <div className="overflow-x-auto pb-1">
      <div className="min-w-[1040px]">
        <div className="mb-2 grid grid-cols-13 gap-1.5">
          {BANDS.map((b) => (
            <div key={b.label} style={{ gridColumn: `${b.from} / ${b.to + 1}` }} className={cn("rounded-md px-2 py-1 text-center text-2xs font-semibold tracking-wide uppercase", b.mvp ? "bg-primary-soft text-primary-strong" : "bg-surface-2 text-fg-subtle")}>
              {b.label}{b.mvp ? " (Phases 7-11)" : ""}
            </div>
          ))}
        </div>
        <ol className="grid grid-cols-13 gap-1.5" aria-label="Delivery lifecycle">
          {PHASES.map((ph) => {
            const state = project ? project.phases[ph.number - 1]!.state : portfolioPhase(world, ph.number).state;
            const count = project ? null : portfolioPhase(world, ph.number).projects.length;
            const meta = PHASE_STATE[state];
            const Icon = STATE_ICON[state];
            const gate = GATE[gateState(world, ph.number, project)];
            const GateIcon = gate.icon;
            const isSelected = selected === ph.number;
            return (
              <li key={ph.number} className="flex flex-col">
                <button
                  type="button"
                  onClick={() => onSelect(ph.number)}
                  aria-pressed={isSelected}
                  aria-label={`Phase ${ph.number}, ${ph.name}: ${meta.label}${count !== null ? `, ${count} project${count === 1 ? "" : "s"}` : ""}`}
                  className={cn(
                    "flex min-h-36 flex-1 flex-col items-center gap-1.5 rounded-xl border p-2 text-center transition-colors",
                    isSelected ? "border-primary bg-primary-soft" : ph.mvp ? "border-primary/25 bg-surface hover:bg-surface-2" : "border-line bg-surface hover:bg-surface-2",
                  )}
                >
                  <span className={cn("grid size-9 place-items-center rounded-full text-sm font-semibold", TONE_SOFT[meta.tone], state === "active" && "ring-2 ring-primary/40")}>
                    {state === "completed" || state === "blocked" || state === "awaiting_approval" ? <Icon className="size-4" aria-hidden /> : ph.number}
                  </span>
                  <span className="text-[11px] leading-tight font-medium text-fg">{ph.name}</span>
                  <span className={cn("text-[10px]", TONE_TEXT[meta.tone])}>{meta.label}</span>
                  {count !== null && count > 0 && <span className="text-[10px] font-semibold text-fg">{count} project{count === 1 ? "" : "s"}</span>}
                  {!ph.mvp && <Tag className="mt-auto h-4 px-1 text-[9px]">Preview</Tag>}
                </button>
                <div className={cn("mt-1.5 flex items-center justify-center gap-1 rounded-md px-1 py-1 text-[9px] font-medium", TONE_SOFT[gate.tone])} title={`${ph.gate}: ${gate.label}`}>
                  <GateIcon className="size-3 shrink-0" aria-hidden />
                  <span className="truncate">{gate.label}</span>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
