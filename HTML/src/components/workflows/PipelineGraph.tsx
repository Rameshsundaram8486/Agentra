/* The delivery pipeline as a live graph: agent stages (Phases 7-11) with human approval gates between them, and the
   Project Owner Agent overseeing all of them. Counts come from the records; an edge animates while work flows. */
import { useMemo } from "react";
import { Background, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Bot, Radar, UserCheck } from "lucide-react";
import { cn } from "@/components/ui/cn";
import { gateDecisions, stageStats, type StageStats } from "@/store/operations";
import { agentType } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import type { World } from "@/types";

type StageData = { kind: "stage"; label: string; phase: string; stats: StageStats; selected: boolean };
type GateData = { kind: "gate"; label: string; waiting: number; selected: boolean };
type OwnerData = { kind: "owner"; label: string; working: boolean; selected: boolean };

function StageNode({ data }: NodeProps<Node<StageData>>) {
  const { stats } = data;
  const tone = stats.blocked ? "border-warning" : stats.working ? "border-primary" : stats.waiting ? "border-violet" : "border-line-strong";
  return (
    <div className={cn("w-[176px] rounded-xl border-2 bg-surface px-3 py-2.5 text-left shadow-panel transition-colors", tone, data.selected && "ring-2 ring-primary-strong ring-offset-2 ring-offset-bg")}>
      <Handle type="target" position={Position.Left} className="!size-2 !border-0 !bg-line-strong" />
      <Handle type="source" position={Position.Right} className="!size-2 !border-0 !bg-line-strong" />
      <Handle type="target" id="top" position={Position.Top} className="!size-1.5 !border-0 !bg-transparent" />
      <div className="flex items-center gap-2">
        <span className={cn("grid size-7 place-items-center rounded-lg", stats.working ? "bg-primary-soft text-primary-strong" : "bg-surface-2 text-fg-subtle")}>
          <Bot className="size-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <div className="truncate text-[12px] font-semibold text-fg">{data.label}</div>
          <div className="text-[10px] text-fg-subtle">{data.phase}</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1 text-center">
        <div className="rounded bg-surface-2 py-0.5"><div className="text-[13px] font-semibold text-primary-strong tabular">{stats.working}</div><div className="text-[9px] text-fg-subtle">working</div></div>
        <div className="rounded bg-surface-2 py-0.5"><div className="text-[13px] font-semibold text-violet tabular">{stats.waiting}</div><div className="text-[9px] text-fg-subtle">waiting</div></div>
        <div className="rounded bg-surface-2 py-0.5"><div className={cn("text-[13px] font-semibold tabular", stats.failed ? "text-danger" : "text-fg-subtle")}>{stats.failed}</div><div className="text-[9px] text-fg-subtle">failed</div></div>
      </div>
      {stats.working > 0 && <div className="mt-1.5 flex items-center gap-1 text-[10px] text-primary-strong"><span className="live-pulse size-1.5 rounded-full bg-primary" />running now</div>}
    </div>
  );
}

function GateNode({ data }: NodeProps<Node<GateData>>) {
  return (
    <div className={cn("flex w-[112px] flex-col items-center gap-1 rounded-xl border border-dashed px-2 py-2 text-center", data.waiting ? "border-violet bg-violet-soft" : "border-line-strong bg-surface", data.selected && "ring-2 ring-primary-strong ring-offset-2 ring-offset-bg")}>
      <Handle type="target" position={Position.Left} className="!size-2 !border-0 !bg-line-strong" />
      <Handle type="source" position={Position.Right} className="!size-2 !border-0 !bg-line-strong" />
      <UserCheck className={cn("size-4", data.waiting ? "text-violet" : "text-fg-subtle")} aria-hidden />
      <div className="text-[10px] leading-tight font-medium text-fg">{data.label}</div>
      <div className={cn("text-[10px]", data.waiting ? "font-semibold text-violet" : "text-fg-subtle")}>{data.waiting ? `${data.waiting} waiting for people` : "nothing waiting"}</div>
    </div>
  );
}

function OwnerNode({ data }: NodeProps<Node<OwnerData>>) {
  return (
    <div className={cn("flex items-center gap-2 rounded-full border-2 border-cyan bg-surface px-4 py-2 shadow-panel", data.selected && "ring-2 ring-primary-strong ring-offset-2 ring-offset-bg")}>
      <Handle type="source" position={Position.Bottom} className="!size-2 !border-0 !bg-cyan" />
      <Radar className="size-4 text-cyan" aria-hidden />
      <span className="text-[12px] font-semibold text-fg">{data.label}</span>
      {data.working && <span className="text-[10px] text-cyan">monitoring</span>}
    </div>
  );
}

const NODE_TYPES = { stage: StageNode, gate: GateNode, owner: OwnerNode };

/** The pipeline: phase, agent type, and the gate that follows it. */
export const PIPELINE = [
  { id: "business_analyst", phase: 7, gate: "Requirements baseline" },
  { id: "solution_architect", phase: 8, gate: "Design and backlog" },
  { id: "developer", phase: 9, gate: "Change sets" },
  { id: "qa_tester", phase: 10, gate: "QA report" },
  { id: "uat_release", phase: 11, gate: "Customer sign-off" },
] as const;

export function PipelineGraph({ world, selected, onSelect }: { world: World; selected: string | null; onSelect: (id: string) => void }) {
  const theme = useDemo((s) => s.theme);
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const step = 290;
    PIPELINE.forEach((stage, i) => {
      const stats = stageStats(world, stage.id);
      nodes.push({ id: stage.id, type: "stage", position: { x: i * step, y: 150 }, data: { kind: "stage", label: agentType(world, stage.id)!.name, phase: `Phase ${stage.phase}`, stats, selected: selected === stage.id } });
      nodes.push({ id: `gate-${stage.phase}`, type: "gate", position: { x: i * step + 192, y: 162 }, data: { kind: "gate", label: stage.gate, waiting: gateDecisions(world, stage.phase).length, selected: selected === `gate-${stage.phase}` } });
      edges.push({ id: `e-${stage.id}-gate`, source: stage.id, target: `gate-${stage.phase}`, animated: stats.working > 0, style: { stroke: "var(--primary)", strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: "var(--primary)" } });
      const next = PIPELINE[i + 1];
      if (next) {
        edges.push({ id: `e-gate-${stage.phase}-${next.id}`, source: `gate-${stage.phase}`, target: next.id,
          style: { stroke: "var(--line-strong)", strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: "var(--line-strong)" } });
      }
    });
    const security = stageStats(world, "security_reviewer");
    nodes.push({ id: "security_reviewer", type: "stage", position: { x: step, y: 330 }, data: { kind: "stage", label: "Security Reviewer Agent", phase: "Phase 8 review", stats: security, selected: selected === "security_reviewer" } });
    edges.push({ id: "e-sa-sec", source: "solution_architect", target: "security_reviewer", targetHandle: "top", type: "smoothstep", animated: security.working > 0, style: { stroke: "var(--violet)", strokeDasharray: "4 3" } });
    const owner = world.agents.find((a) => a.typeKey === "project_owner");
    nodes.push({ id: "project_owner", type: "owner", position: { x: 2 * step - 40, y: 0 }, data: { kind: "owner", label: "Project Owner Agent", working: owner?.status === "working", selected: selected === "project_owner" } });
    PIPELINE.forEach((stage) => edges.push({ id: `e-po-${stage.id}`, source: "project_owner", target: stage.id, targetHandle: "top", style: { stroke: "var(--cyan)", strokeWidth: 1, strokeDasharray: "3 4", opacity: 0.6 } }));
    return { nodes, edges };
  }, [world, selected]);

  return (
    <div className="h-[440px] w-full overflow-hidden rounded-lg border border-line bg-bg" aria-label="Delivery pipeline: agents, approval gates and handoffs" role="figure">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        forceColorMode={theme}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, node) => onSelect(node.id)}
        minZoom={0.3}
        maxZoom={1.6}
        style={{ background: "transparent" }}
      >
        <Background gap={20} size={1} color="var(--line)" />
      </ReactFlow>
    </div>
  );
}
