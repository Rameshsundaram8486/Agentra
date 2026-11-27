import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { at } from "@/data/time";
import { invariantProblems } from "@/test/invariants";
import { byId, completion, currentPhase, healthDistribution, kpis, projectHealth } from "./selectors";

describe("the seed world", () => {
  const world = createSeedWorld();

  it("is internally consistent", () => {
    expect(invariantProblems(world)).toEqual([]);
  });

  it("has the size the brief asks for", () => {
    expect(world.customers).toHaveLength(4);
    expect(world.projects.length).toBeGreaterThanOrEqual(6);
    expect(world.agents.length).toBeGreaterThanOrEqual(20);
    expect(world.agents.length).toBeLessThanOrEqual(25);
    expect(world.tasks.length).toBeGreaterThanOrEqual(30);
    expect(world.decisions.length).toBeGreaterThanOrEqual(10);
    expect(world.risks.length).toBeGreaterThanOrEqual(5);
    expect(world.executions.length).toBeGreaterThanOrEqual(5);
  });

  it("derives project health from records, with one project in each situation", () => {
    const health = Object.fromEntries(world.projects.map((p) => [p.id, projectHealth(world, p).health]));
    expect(health).toEqual({
      "p-spo": "critical", // RSK-001 (score 16) and the overdue escalation DEC-006
      "p-intranet": "at_risk", // RSK-003, INC-002, the blocked performance test
      "p-power": "on_track",
      "p-docai": "on_hold",
      "p-spse": "on_track",
      "p-workflow": "on_track",
      "p-ess": "completed",
    });
    expect(projectHealth(world, byId(world.projects, "p-spo")!).reasons[0]).toContain("RSK-001");
    expect(healthDistribution(world)).toEqual({ on_track: 3, at_risk: 1, critical: 1, on_hold: 1, completed: 1 });
  });

  it("computes the current phase and completion of each project", () => {
    const phases = Object.fromEntries(world.projects.map((p) => [p.code, currentPhase(p).phase]));
    expect(phases).toEqual({ "ANT-SPO": 9, "MPL-INT": 10, "ORH-PPA": 8, "ORH-ADP": 5, "MPL-SSE": 11, "SBH-EWM": 7, "SBH-ESS": 13 });
    expect(completion(byId(world.projects, "p-ess")!)).toBe(100);
    expect(completion(byId(world.projects, "p-spo")!)).toBe(Math.round((8 * 100 + 58) / 13));
  });

  it("computes the KPIs from the same records", () => {
    expect(kpis(world)).toEqual({
      activeProjects: 5,
      activeAgents: world.agents.filter((a) => a.status === "working").length,
      tasksRunning: 3,
      pendingDecisions: 9,
      overdueDecisions: 1,
      projectsAtRisk: 2,
      completedDeliverables: world.artifacts.filter((a) => a.versions[a.versions.length - 1]!.status === "approved").length,
    });
  });

  it("starts the clock at the demo start", () => {
    expect(world.now).toBe(at(0));
  });

  it("returns a fresh copy each time, so a reset never shares state", () => {
    const again = createSeedWorld();
    again.projects[0]!.name = "Changed";
    expect(createSeedWorld().projects[0]!.name).not.toBe("Changed");
  });
});
