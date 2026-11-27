/* Links from a project or a phase to the reports in Reports and Analytics, filtered to that project where the report
   supports it. */
import { ArrowRight, FileText } from "lucide-react";
import { Link } from "react-router";
import { Panel } from "@/components/ui/Panel";
import { REPORTS } from "@/store/reports";

export function ReportLinks({ projectId, ids, title = "Reports" }: { projectId?: string; ids?: string[]; title?: string }) {
  const reports = REPORTS.filter((r) => (ids ? ids.includes(r.id) : r.projectFilter));
  return (
    <Panel title={title} subtitle="Built from the records at this moment; preview, CSV and PDF in Reports and Analytics" icon={FileText} flush>
      <ul className="divide-y divide-line">
        {reports.map((r) => (
          <li key={r.id}>
            <Link to={`/reports?report=${r.id}${projectId && r.projectFilter ? `&project=${projectId}` : ""}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2">
              <FileText className="size-4 shrink-0 text-fg-subtle" aria-hidden />
              <span className="min-w-0 flex-1 text-[13px]">{r.title}<span className="block text-2xs text-fg-subtle">{r.description}{projectId && !r.projectFilter ? " (whole company)" : ""}</span></span>
              <ArrowRight className="size-4 text-fg-subtle" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
