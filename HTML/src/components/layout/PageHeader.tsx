import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

export interface Crumb {
  label: string;
  to?: string;
}

/** The top of every page: where you are, what the page is, and its main actions. */
export function PageHeader({ title, description, crumbs = [], meta, actions }: { title: ReactNode; description?: ReactNode; crumbs?: Crumb[]; meta?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {crumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-1 flex flex-wrap items-center gap-1 text-xs text-fg-subtle">
            {crumbs.map((crumb, index) => (
              <span key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                {index > 0 && <ChevronRight className="size-3" aria-hidden />}
                {crumb.to ? <Link to={crumb.to} className="hover:text-fg">{crumb.label}</Link> : <span>{crumb.label}</span>}
              </span>
            ))}
          </nav>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
          {meta}
        </div>
        {description && <p className="mt-1 max-w-3xl text-[13px] text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
