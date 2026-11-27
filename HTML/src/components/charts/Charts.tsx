/* Charts for the Command Center. Colours are theme tokens (CSS variables), so charts follow dark and light themes;
   every chart has a text summary for screen readers and its numbers in tooltips. */
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router";
import { cn } from "@/components/ui/cn";
import { HEALTH, TONE_DOT, TONE_SOFT, TONE_VAR } from "@/components/ui/status";
import { PHASES } from "@/data/lifecycle";
import { agentActivity, lifecyclePositions, riskMatrix, taskTrend } from "@/store/analytics";
import { healthDistribution } from "@/store/selectors";
import type { Health, World } from "@/types";

const AXIS = { fontSize: 11, fill: "var(--fg-subtle)" };
const TOOLTIP = {
  contentStyle: { background: "var(--surface-3)", border: "1px solid var(--line-strong)", borderRadius: 8, fontSize: 12, color: "var(--fg)" },
  labelStyle: { color: "var(--fg)", fontWeight: 600 },
  itemStyle: { color: "var(--fg-muted)" },
  cursor: { fill: "var(--surface-2)" },
};

export function HealthDonut({ world }: { world: World }) {
  const counts = healthDistribution(world);
  const data = (Object.keys(counts) as Health[]).filter((h) => counts[h] > 0).map((h) => ({ key: h, name: HEALTH[h].label, value: counts[h] }));
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="flex items-center gap-4">
      <div className="relative size-36 shrink-0" role="img" aria-label={`Project health: ${data.map((d) => `${d.value} ${d.name.toLowerCase()}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="68%" outerRadius="100%" paddingAngle={2} stroke="none" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.key} fill={TONE_VAR[HEALTH[d.key].tone]} />)}
            </Pie>
            <Tooltip {...TOOLTIP} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="text-2xl font-semibold tabular">{total}</div>
            <div className="text-2xs text-fg-subtle">projects</div>
          </div>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-1.5">
        {data.map((d) => (
          <li key={d.key} className="flex items-center gap-2 text-[13px]">
            <span className={cn("size-2.5 rounded-sm", TONE_DOT[HEALTH[d.key].tone])} aria-hidden />
            <span className="flex-1 text-fg-muted">{d.name}</span>
            <span className="font-medium tabular">{d.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TaskTrendChart({ world }: { world: World }) {
  const data = taskTrend(world);
  const last = data.at(-1)!;
  return (
    <div role="img" aria-label={`Tasks completed: ${last.total} in total; ${data.reduce((s, d) => s + d.completed, 0)} in the last 14 days`} className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} interval={3} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip {...TOOLTIP} />
          <Area type="monotone" dataKey="total" name="Completed (running total)" stroke="var(--primary)" strokeWidth={2} fill="url(#trend-fill)" isAnimationActive={false} />
          <Area type="monotone" dataKey="completed" name="Completed that day" stroke="var(--success)" strokeWidth={1.5} fill="none" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AgentActivityChart({ world }: { world: World }) {
  const data = agentActivity(world);
  return (
    <div role="img" aria-label={`Agent runs by category: ${data.map((d) => `${d.category} ${d.succeeded} succeeded, ${d.failed} failed`).join("; ")}`} className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 4 }} barCategoryGap={5}>
          <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
          <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="category" tick={AXIS} tickLine={false} axisLine={false} width={118} interval={0} />
          <Tooltip {...TOOLTIP} />
          <Bar dataKey="succeeded" name="Succeeded" stackId="runs" fill="var(--primary)" radius={[0, 0, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="failed" name="Failed" stackId="runs" fill="var(--danger)" radius={[0, 3, 3, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RISK_SHADE = (likelihood: number, impact: number) => {
  const score = likelihood * impact;
  return score >= 16 ? "bg-danger-soft" : score >= 12 ? "bg-warning-soft" : score >= 6 ? "bg-primary-soft" : "bg-surface-2";
};

export function RiskMatrix({ world }: { world: World }) {
  const cells = riskMatrix(world);
  const open = cells.reduce((s, c) => s + c.codes.length, 0);
  return (
    <div>
      <div className="flex gap-2">
        <div className="flex w-4 items-center justify-center text-2xs text-fg-subtle [writing-mode:vertical-rl] rotate-180">Likelihood</div>
        <div className="grid flex-1 grid-cols-5 gap-1" role="grid" aria-label={`${open} open risks by likelihood and impact`}>
          {cells.map((cell) => (
            <div
              key={`${cell.likelihood}-${cell.impact}`}
              role="gridcell"
              title={cell.codes.length ? `${cell.codes.join(", ")}: likelihood ${cell.likelihood}, impact ${cell.impact}` : `Likelihood ${cell.likelihood}, impact ${cell.impact}`}
              className={cn("flex h-8 items-center justify-center rounded-md text-2xs font-semibold", RISK_SHADE(cell.likelihood, cell.impact), cell.codes.length ? "text-fg" : "text-transparent")}
            >
              {cell.codes.length || "·"}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-1 pl-6 text-center text-2xs text-fg-subtle">Impact</div>
    </div>
  );
}

/** Every project at its place in the 13-phase lifecycle, with the MVP phases highlighted. */
export function LifecycleStrip({ world }: { world: World }) {
  const positions = lifecyclePositions(world);
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[760px] grid-cols-13 gap-1.5">
        {PHASES.map((phase) => {
          const here = positions.filter((p) => (p.health === "completed" ? 13 : p.phase.phase) === phase.number);
          return (
            <div key={phase.number} className={cn("flex min-h-28 flex-col rounded-lg border p-1.5", phase.mvp ? "border-primary/30 bg-primary-soft/40" : "border-line bg-surface-2/40")}>
              <div className="text-center">
                <div className="text-2xs font-semibold text-fg-muted tabular">{phase.number}</div>
                <div className="truncate text-[10px] text-fg-subtle" title={phase.name}>{phase.short}</div>
              </div>
              <div className="mt-1.5 flex flex-1 flex-col gap-1">
                {here.map(({ project, health }) => (
                  <Link
                    key={project.id}
                    to={`/projects/${project.id}`}
                    title={`${project.name}: ${HEALTH[health].label}`}
                    className={cn("truncate rounded px-1 py-1 text-center text-2xs font-semibold hover:ring-1 hover:ring-line-strong", TONE_SOFT[HEALTH[health].tone])}
                  >
                    {project.code}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-2xs text-fg-subtle"><span className="mr-1 inline-block size-2 rounded-sm border border-primary/40 bg-primary-soft align-middle" />Phases 7 to 11 are the MVP; the others are previews.</p>
    </div>
  );
}
