import type { ReactNode } from "react";
import { LoaderCircle, type LucideIcon } from "lucide-react";
import { cn } from "./cn";
import { TONE_DOT, TONE_SOFT, type StatusMeta, type Tone } from "./status";

/** A status from the shared vocabulary: icon, label and tone together, never colour alone. */
export function StatusPill({ meta, size = "md", spin = true, className }: { meta: StatusMeta; size?: "sm" | "md"; spin?: boolean; className?: string }) {
  const Icon = meta.icon;
  const spinning = spin && Icon === LoaderCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap",
        size === "sm" ? "h-5 px-1.5 text-2xs" : "h-6 px-2 text-xs",
        TONE_SOFT[meta.tone],
        className,
      )}
    >
      <Icon className={cn(size === "sm" ? "size-3" : "size-3.5", spinning && "animate-spin [animation-duration:2.4s]")} aria-hidden />
      {meta.label}
    </span>
  );
}

/** A small neutral or toned label, e.g. a phase, an ID or "Preview". */
export function Tag({ children, tone = "neutral", icon: Icon, className, title }: { children: ReactNode; tone?: Tone; icon?: LucideIcon; className?: string; title?: string }) {
  return (
    <span title={title} className={cn("inline-flex h-5 items-center gap-1 rounded-md px-1.5 text-2xs font-medium whitespace-nowrap", TONE_SOFT[tone], className)}>
      {Icon && <Icon className="size-3" aria-hidden />}
      {children}
    </span>
  );
}

export function Dot({ tone, pulse, className }: { tone: Tone; pulse?: boolean; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-full", TONE_DOT[tone], pulse && "live-pulse", className)} />;
}

/** A count bubble for navigation and the top bar. */
export function CountBadge({ count, tone = "primary", label }: { count: number; tone?: Tone; label?: string }) {
  if (count <= 0) return null;
  return (
    <span aria-label={label ?? `${count}`} className={cn("inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-2xs font-semibold tabular", TONE_SOFT[tone])}>
      {count > 99 ? "99+" : count}
    </span>
  );
}
