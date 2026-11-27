import type { ReactNode } from "react";
import { Inbox, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import { cn } from "./cn";
import { TONE_DOT, type Tone } from "./status";

export function EmptyState({ title, hint, icon: Icon = Inbox, action }: { title: ReactNode; hint?: ReactNode; icon?: LucideIcon; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-surface-2 text-fg-subtle">
        <Icon className="size-5" aria-hidden />
      </span>
      <p className="text-sm font-medium text-fg">{title}</p>
      {hint && <p className="max-w-sm text-[13px] text-fg-muted">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title, detail, action }: { title: ReactNode; detail?: ReactNode; action?: ReactNode }) {
  return <EmptyState icon={TriangleExclamationPoint} title={title} hint={detail} action={action} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-md bg-surface-2", className)} />;
}

/** A thin progress bar with an accessible value. */
export function Progress({ value, tone = "primary", label, className }: { value: number; tone?: Tone; label?: string; className?: string }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div role="progressbar" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100} aria-label={label} className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div className={cn("h-full rounded-full transition-[width] duration-500", TONE_DOT[tone])} style={{ width: `${clamped}%` }} />
    </div>
  );
}
