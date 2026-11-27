import type { HTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "./cn";

interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  flush?: boolean; // no body padding (tables, lists)
  children?: ReactNode;
}

/** The standard surface: a titled section with optional actions. */
export function Panel({ title, subtitle, icon: Icon, actions, flush, className, children, ...props }: PanelProps) {
  return (
    <section className={cn("flex min-w-0 flex-col rounded-[var(--radius-panel)] border border-line bg-surface shadow-panel", className)} {...props}>
      {(title || actions) && (
        <header className="flex min-h-12 items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            {Icon && <Icon className="size-4 shrink-0 text-fg-subtle" aria-hidden />}
            <div className="min-w-0">
              {title && <h2 className="truncate text-sm font-semibold text-fg">{title}</h2>}
              {subtitle && <p className="truncate text-xs text-fg-subtle">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={cn("min-h-0 flex-1", !flush && "p-4")}>{children}</div>
    </section>
  );
}

/** A label and value pair for detail panels. */
export function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-2xs font-medium tracking-wide text-fg-subtle uppercase">{label}</dt>
      <dd className="mt-0.5 text-[13px] text-fg">{children}</dd>
    </div>
  );
}
