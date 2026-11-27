/* The simulation engine. Time moves in ticks (one real second at 1x speed; each tick is TICK_SECONDS of simulated
   time). Each tick: running executions write log lines, retried runs finish when due, reactions whose precondition
   now holds fire (follow-ups to human decisions, whatever the timeline has reached), and the next timeline event
   fires once its delay has passed. A timeline event whose precondition (`when`) is not met waits and is checked
   again on every later tick, so nothing happens that depends on a decision nobody has made, or on a run a person
   paused. Everything is deterministic: the same ticks from the same world always give the same result. */
import type { World } from "@/types";
import { addSeconds, secondsBetween, TICK_SECONDS } from "@/data/time";
import { answerClarification, logActivity, mutate } from "@/store/actions";
import { briefing } from "@/store/briefing";
import { agentType, byId } from "@/store/selectors";
import { REACTIONS, TIMELINE, type ScenarioEvent } from "./scenario";

export interface Script {
  timeline: ScenarioEvent[];
  reactions: ScenarioEvent[];
}

export const SCRIPT: Script = { timeline: TIMELINE, reactions: REACTIONS };

const LOG_EVERY = 3;

/** Once the script has run out, the Project Owner Agent keeps scanning, so a live demo never goes silent. */
const SCAN_EVERY = 45;

function ownerScan(world: World, script: Script): void {
  if (world.sim.cursor < script.timeline.length || world.sim.elapsed % SCAN_EVERY !== 0) return;
  const brief = briefing(world);
  logActivity(world, brief.status === "critical" ? "warning" : "info", `Project Owner Agent scan: ${brief.headline} Health score ${brief.score}.`, { agentId: "a-po", link: "/owner" });
}

const PROGRESS_LINES: Record<string, string[]> = {
  developer: ["Reading the affected modules", "Writing the change and its unit tests", "Running the change set checks", "Preparing the change summary"],
  qa_tester: ["Suite finished; collecting results", "Retrying a flaky case once", "Comparing results with the previous run", "Linking failures to defects"],
  security_reviewer: ["Checking access control items", "Checking data protection items", "Checking logging and monitoring items", "Writing findings"],
  business_analyst: ["Mapping answers to requirements", "Writing acceptance criteria", "Checking traceability", "Running quality checks"],
  project_owner: ["Checking decision deadlines", "Checking stuck tasks", "Comparing progress with milestones", "Summarising findings"],
  default: ["Working", "Checking inputs", "Preparing output", "Validating output"],
};

function heartbeat(world: World): void {
  for (const execution of world.executions) {
    if (execution.status === "retrying") {
      execution.status = "running";
      execution.logs.push({ at: world.now, level: "info", text: `Attempt ${execution.attempt} of ${execution.maxAttempts + 1} started` });
      continue;
    }
    if (execution.status !== "running") continue;
    if (execution.finishAt !== undefined && world.sim.elapsed >= execution.finishAt) {
      finishRetried(world, execution.id);
      continue;
    }
    if (world.sim.elapsed % LOG_EVERY === 0) {
      const typeKey = byId(world.agents, execution.agentId)?.typeKey ?? "default";
      const lines = PROGRESS_LINES[typeKey] ?? PROGRESS_LINES.default!;
      execution.logs.push({ at: world.now, level: "info", text: lines[execution.logs.length % lines.length]! });
      if (execution.logs.length > 40) execution.logs.splice(0, execution.logs.length - 40);
    }
  }
}

/** A run a person retried finishes successfully; its task goes to review and its agent waits for approval. */
function finishRetried(world: World, executionId: string): void {
  const execution = byId(world.executions, executionId)!;
  Object.assign(execution, { status: "succeeded", endedAt: world.now, finishAt: undefined, output: execution.output ?? "Completed on retry; output ready for review" });
  execution.logs.push({ at: world.now, level: "info", text: "Run succeeded on retry" });
  const task = byId(world.tasks, execution.taskId);
  if (task && task.state === "in_progress") task.state = "waiting_for_review";
  const agent = byId(world.agents, execution.agentId);
  if (agent && agent.status === "working") Object.assign(agent, { status: task ? "waiting_approval" : "completed", since: world.now });
  const name = agent ? agentType(world, agent.typeKey)?.name ?? agent.name : "Agent";
  logActivity(world, "success", `${agent?.name ?? name}: "${execution.title}" succeeded on retry`, { projectId: execution.projectId, agentId: execution.agentId });
}

/** Agents answer a question about their recommendation two ticks after it is asked. */
const ANSWER_AFTER_TICKS = 2;

function answerQuestions(world: World): void {
  for (const decision of world.decisions) {
    if (decision.status !== "clarification_requested") continue;
    const asked = [...decision.history].reverse().find((e) => e.action === "clarify");
    if (!asked || secondsBetween(asked.at, world.now) >= ANSWER_AFTER_TICKS * TICK_SECONDS) answerClarification(world, decision);
  }
}

function fire(world: World, event: ScenarioEvent): void {
  event.apply(world);
  world.sim.done.push(event.id);
}

/** Advances the world by `ticks`; returns a new world. */
export function advance(world: World, ticks = 1, script: Script = SCRIPT): World {
  return mutate(world, (draft) => {
    for (let i = 0; i < ticks; i++) {
      draft.sim.elapsed += 1;
      draft.now = addSeconds(draft.now, TICK_SECONDS);
      heartbeat(draft);
      answerQuestions(draft);
      // Timeline events that were waiting, and reactions, whose precondition now holds.
      for (const event of [...script.timeline.slice(0, draft.sim.cursor), ...script.reactions]) {
        if (!draft.sim.done.includes(event.id) && event.when?.(draft)) fire(draft, event);
      }
      // The next timeline event, once its delay has passed.
      while (draft.sim.cursor < script.timeline.length) {
        const event = script.timeline[draft.sim.cursor]!;
        if (draft.sim.elapsed - draft.sim.lastEventAt < event.after) break;
        draft.sim.cursor += 1;
        draft.sim.lastEventAt = draft.sim.elapsed;
        if (!event.when || event.when(draft)) fire(draft, event);
      }
      ownerScan(draft, script);
    }
  });
}

/** How far the script has got: events fired, events waiting for a precondition, and the total. */
export function scenarioProgress(world: World, script: Script = SCRIPT): { fired: number; waiting: number; total: number } {
  const all = [...script.timeline, ...script.reactions];
  return { fired: world.sim.done.length, waiting: all.filter((e) => !world.sim.done.includes(e.id)).length, total: all.length };
}
