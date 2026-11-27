import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "./cn";
import { TONE_SOFT, type Tone } from "./status";

interface KpiProps {
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  tone?: Tone;
  hint?: ReactNode; // the context that makes the number meaningful
  onClick?: () => void;
  className?: string;
}

/** A key figure with the context behind it. Clickable when it leads somewhere. */
export function Kpi({ label, value, icon: Icon, tone = "primary", hint, onClick, className }: KpiProps) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-fg-muted">{label}</span>
        <span className={cn("grid size-7 place-items-center rounded-lg", TONE_SOFT[tone])}>
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <div className="mt-1 text-[28px] leading-8 font-semibold tracking-tight text-fg tabular">{value}</div>
      {hint && <div className="mt-1 truncate text-xs text-fg-subtle">{hint}</div>}
    </>
  );
  const classes = cn("min-w-0 rounded-[var(--radius-panel)] border border-line bg-surface p-3.5 text-left shadow-panel", className);
  return onClick ? (
    <button type="button" onClick={onClick} className={cn(classes, "transition-colors hover:border-line-strong hover:bg-surface-2")}>
      {body}
    </button>
  ) : (
    <div className={classes}>{body}</div>
  );
}
