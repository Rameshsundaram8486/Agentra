/* What a page shows until its build stage: its purpose, when it arrives, and, where it can, the live records that
   belong to it already, so no navigation item is a dead end. */
import { Construction } from "lucide-react";
import { Link, useLocation, useParams } from "react-router";
import { NAVIGATION, navItemFor, type NavItem } from "@/app/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusPill, Tag } from "@/components/ui/Badge";
import { Panel } from "@/components/ui/Panel";
import { EmptyState, Progress } from "@/components/ui/States";
import { HEALTH } from "@/components/ui/status";
import { phaseDef } from "@/data/lifecycle";
import { byId, completion, currentPhase, projectHealth } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { Project } from "@/types";

function ProjectList({ projects }: { projects: Project[] }) {
  const world = useDemo((s) => s.world);
  if (projects.length === 0) return <p className="text-[13px] text-fg-muted">No project is in this phase right now.</p>;
  return (
    <ul className="divide-y divide-line">
      {projects.map((p) => (
        <li key={p.id} className="flex flex-wrap items-center gap-3 py-2.5">
          <Link to={`/projects/${p.id}`} className="min-w-0 flex-1">
            <span className="block font-medium hover:text-primary-strong">{p.name}</span>
            <span className="block text-xs text-fg-subtle">{byId(world.customers, p.customerId)?.name} · Phase {currentPhase(p).phase}, {phaseDef(currentPhase(p).phase).short}</span>
          </Link>
          <div className="flex w-32 items-center gap-2"><Progress value={completion(p)} label={`${p.name} completion`} /><span className="text-xs tabular">{completion(p)}%</span></div>
          <StatusPill meta={HEALTH[projectHealth(world, p).health]} />
        </li>
      ))}
    </ul>
  );
}

export function Placeholder({ item: given }: { item?: NavItem }) {
  const location = useLocation();
  const { projectId } = useParams();
  const world = useDemo((s) => s.world);
  const role = useDemo((s) => s.role);
  const project = projectId ? byId(world.projects, projectId) : undefined;
  const item = given ?? navItemFor(location.pathname);
  const group = NAVIGATION.find((g) => g.items.some((i) => i.id === item?.id));

  if (projectId) {
    return (
      <>
        <PageHeader title={project?.name ?? "Project"} crumbs={[{ label: "Projects", to: "/projects" }, { label: project?.code ?? projectId }]} description={project?.summary}
          meta={<Tag tone="primary">Arrives in Stage 4</Tag>} />
        <Panel><EmptyState icon={Construction} title="The project workspace arrives in Stage 4" hint="Overview, lifecycle, agents, tasks, requirements, architecture, development, QA, UAT, decisions, risks, documents and reports for this project." /></Panel>
      </>
    );
  }
  if (!item) {
    return (
      <Panel>
        <EmptyState title="This page does not exist" hint={`Nothing is at ${location.pathname}.`} action={<Link to="/" className="text-[13px] text-primary-strong hover:underline">Go to the Executive Command Center</Link>} />
      </Panel>
    );
  }
  const phaseProjects = item.phase !== undefined ? world.projects.filter((p) => p.status !== "completed" && currentPhase(p).phase === item.phase) : [];
  const count = item.count?.(world, role);
  return (
    <>
      <PageHeader
        title={item.label}
        crumbs={[{ label: group?.label ?? "" }]}
        description={item.description}
        meta={<>{item.preview && <Tag tone="warning" title="Outside the MVP (Phases 7-11)">Preview, not in the MVP</Tag>}<Tag tone="primary">Arrives in Stage {item.stage}</Tag></>}
      />
      <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
        <Panel>
          <EmptyState icon={Construction} title={`${item.label} arrives in Stage ${item.stage}`} hint={item.description} />
        </Panel>
        <Panel title="Already in the demo data" subtitle="Live records this page will show">
          {item.phase !== undefined ? (
            <>
              <p className="mb-2 text-[13px] text-fg-muted">Phase {item.phase}: {phaseDef(item.phase).name}. Gate: {phaseDef(item.phase).gate}.</p>
              <ProjectList projects={phaseProjects} />
            </>
          ) : count ? (
            <p className="text-[13px] text-fg-muted"><span className="text-2xl font-semibold text-fg tabular">{count.value}</span> {count.label}</p>
          ) : (
            <ProjectList projects={world.projects.filter((p) => p.status === "active")} />
          )}
        </Panel>
      </div>
    </>
  );
}
