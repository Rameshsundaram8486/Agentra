import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { bottlenecks, currentRun, executionSeconds, gateDecisions, queues, stageStats, successRate } from "./operations";
import { byId } from "./selectors";

describe("operational views", () => {
  const world = createSeedWorld();

  it("times runs against the simulated clock and stops the clock when they end", () => {
    const running = byId(world.executions, "x-101")!;
    expect(executionSeconds(running, world.now)).toBe(18 * 60);
    expect(executionSeconds(running, advance(world, 3).now)).toBe(18 * 60 + 60);
    const finished = byId(world.executions, "x-105")!;
    expect(executionSeconds(finished, advance(world, 3).now)).toBe(12 * 60);
  });

  it("separates work ready to start, work waiting on other work, and work waiting on people", () => {
    const q = queues(world);
    expect(q.ready.map((t) => t.key).sort()).toEqual(["CR-002", "DEF-014"]);
    expect(q.waitingOnWork.map((t) => t.key)).toEqual(expect.arrayContaining(["WI-006", "WI-007", "QA-09"]));
    expect(q.waitingOnPeople.map((t) => t.key).sort()).toEqual(["BA-02", "SA-02", "UAT-05", "WI-004"]);
  });

  it("finds where work piles up", () => {
    const [top] = bottlenecks(world);
    expect(top!.load).toBeGreaterThan(0);
    expect(bottlenecks(world).map((b) => b.phase).sort((a, b) => a - b)).toEqual([7, 8, 9, 10, 11]);
  });

  it("summarises each pipeline stage and gate from agents, runs and decisions", () => {
    const dev = stageStats(world, "developer");
    expect(dev.agents.map((a) => a.id)).toEqual(["a-dev1", "a-dev2"]);
    expect(dev.working).toBe(1);
    expect(dev.waiting).toBe(1);
    expect(dev.failed).toBe(2);
    expect(gateDecisions(world, 11).map((d) => d.code)).toEqual(["DEC-008", "DEC-009"]);
    expect(currentRun(world, "a-dev1")!.id).toBe("x-101");
    expect(successRate(byId(world.agents, "a-po")!)).toBeGreaterThan(99);
  });
});
