/* Operational views derived from the records: runs in flight, queues, human dependencies, bottlenecks and the
   delivery pipeline as agents and approval gates. */
import type { Agent, Decision, Execution, Task, World } from "@/types";
import { PHASES } from "@/data/lifecycle";
import { secondsBetween } from "@/data/time";
import { isOpenDecision } from "./selectors";

export const IN_FLIGHT: Execution["status"][] = ["running", "retrying", "paused"];

export function executionSeconds(execution: Execution, now: string): number {
  return secondsBetween(execution.startedAt, execution.endedAt ?? now);
}

export function successRate(agent: Agent): number {
  const finished = agent.succeeded + agent.failed;
  return finished === 0 ? 100 : Math.round((agent.succeeded / finished) * 1000) / 10;
}

export function currentRun(world: World, agentId: string): Execution | undefined {
  return world.executions.find((e) => e.agentId === agentId && IN_FLIGHT.includes(e.status));
}

export function runsOf(world: World, agentId: string): Execution[] {
  return world.executions.filter((e) => e.agentId === agentId).sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
}

/** Work waiting to be picked up, waiting on other work, and waiting on people. */
export function queues(world: World) {
  const done = (id: string) => world.tasks.find((t) => t.id === id)?.state === "completed";
  const open = world.tasks.filter((t) => t.state !== "completed" && t.state !== "cancelled");
  const ready = open.filter((t) => (t.state === "ready" || t.state === "not_started") && t.dependsOn.every(done));
  const waitingOnWork = open.filter((t) => t.state === "not_started" && !t.dependsOn.every(done));
  const waitingOnPeople = open.filter((t) => t.state === "waiting_for_review" || t.state === "waiting_for_input");
  return { ready, waitingOnWork, waitingOnPeople };
}

/** The open decisions a task waiting on people depends on (same project and phase). */
export function decisionsFor(world: World, task: Task): Decision[] {
  return world.decisions.filter((d) => isOpenDecision(d) && d.projectId === task.projectId && d.phase === task.phase);
}

export interface Bottleneck {
  phase: number;
  name: string;
  waitingTasks: number;
  pendingDecisions: number;
  blocked: number;
  load: number;
}

/** Where work is piling up in the MVP phases. */
export function bottlenecks(world: World): Bottleneck[] {
  return PHASES.filter((p) => p.mvp)
    .map((p) => {
      const tasks = world.tasks.filter((t) => t.phase === p.number);
      const waitingTasks = tasks.filter((t) => t.state === "waiting_for_review" || t.state === "waiting_for_input").length;
      const blocked = tasks.filter((t) => t.state === "blocked" || t.state === "failed").length;
      const pendingDecisions = world.decisions.filter((d) => isOpenDecision(d) && d.phase === p.number).length;
      return { phase: p.number, name: p.short, waitingTasks, pendingDecisions, blocked, load: waitingTasks + pendingDecisions + blocked * 2 };
    })
    .sort((a, b) => b.load - a.load);
}

/* The delivery pipeline -------------------------------------------------------------------------- */

export interface StageStats {
  typeKey: string;
  agents: Agent[];
  working: number;
  waiting: number;
  blocked: number;
  failed: number;
  running: Execution[];
  handoffs: number; // runs whose output went on to the next agent
}

export function stageStats(world: World, typeKey: string): StageStats {
  const agents = world.agents.filter((a) => a.typeKey === typeKey);
  const ids = new Set(agents.map((a) => a.id));
  const runs = world.executions.filter((e) => ids.has(e.agentId));
  return {
    typeKey,
    agents,
    working: agents.filter((a) => a.status === "working").length,
    waiting: agents.filter((a) => a.status === "waiting_approval").length,
    blocked: agents.filter((a) => a.status === "blocked").length,
    failed: runs.filter((e) => e.status === "failed").length,
    running: runs.filter((e) => e.status === "running" || e.status === "retrying"),
    handoffs: runs.filter((e) => e.status === "succeeded" && e.handoffTo).length,
  };
}

/** Open decisions at a phase gate. */
export function gateDecisions(world: World, phase: number): Decision[] {
  return world.decisions.filter((d) => isOpenDecision(d) && d.phase === phase);
}
