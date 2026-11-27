import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { invariantProblems } from "@/test/invariants";
import { decide, updateIncident, updateRisk } from "./actions";
import { complianceChecks, delays, failedRuns, healthSignals, stuckWork } from "./oversight";
import { byId } from "./selectors";

const PM = ["u-omar", "project_manager"] as const;

describe("the root-cause workflow", () => {
  it("keeps the cause a hypothesis until a person confirms it, and closes only after verification", () => {
    let world = createSeedWorld();
    expect(() => updateIncident(world, "inc-3", "close", ...PM)).toThrow(/must be resolved first/);
    world = updateIncident(world, "inc-3", "resolve", ...PM);
    expect(() => updateIncident(world, "inc-3", "close", ...PM)).toThrow(/Confirm the probable cause of INC-003 before closing it/);
    world = updateIncident(world, "inc-3", "confirm_cause", ...PM);
    expect(byId(world.incidents, "inc-3")!.rca).toMatchObject({ causeConfirmedBy: "u-omar" });
    expect(byId(world.incidents, "inc-3")!.rca.hypothesis).toContain("Eight parallel threads"); // the agent's text is kept
    world = updateIncident(world, "inc-3", "close", ...PM);
    expect(byId(world.incidents, "inc-3")).toMatchObject({ status: "closed", rca: { verifiedBy: "u-omar" } });
    expect(world.audit[0]).toMatchObject({ action: "incident.close", target: "INC-003" });
    expect(invariantProblems(world)).toEqual([]);
  });

  it("only owners and project managers update incidents and risks", () => {
    expect(() => updateIncident(createSeedWorld(), "inc-2", "investigate", "u-priya", "reviewer")).toThrow(/Only an owner or a project manager/);
    expect(() => updateRisk(createSeedWorld(), "r1", "mitigate", "u-daniel", "customer_approver")).toThrow(/Only an owner or a project manager/);
  });

  it("moves a risk from open to mitigating to closed, and health follows", () => {
    let world = updateRisk(createSeedWorld(), "r3", "mitigate", ...PM);
    expect(() => updateRisk(createSeedWorld(), "r3", "close", ...PM)).toThrow(/Start mitigating RSK-003 before closing it/);
    world = updateRisk(world, "r3", "close", ...PM);
    expect(byId(world.risks, "r3")!.status).toBe("closed");
    expect(healthSignals(world, byId(world.projects, "p-intranet")!)[0]!.count).toBe(0);
    expect(invariantProblems(world)).toEqual([]);
  });
});

describe("what the Project Owner Agent watches", () => {
  it("finds failed runs with their incidents, stuck work and delays", () => {
    const world = createSeedWorld();
    expect(failedRuns(world).map((r) => [r.execution.id, r.incident?.code])).toEqual(expect.arrayContaining([["x-107", "INC-003"], ["x-108", "INC-002"]]));
    expect(stuckWork(world).map((s) => s.task.key)).toEqual(expect.arrayContaining(["WI-008"]));
    expect(delays(world).some((d) => d.milestone.title === "Pilot migration complete" && d.kind === "at_risk")).toBe(true);
  });

  it("checks the governance rules against the records", () => {
    const before = complianceChecks(createSeedWorld());
    expect(before.filter((c) => !c.passed).map((c) => c.id)).toEqual(["deadlines"]); // DEC-006 is overdue
    const after = complianceChecks(decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", personId: "u-rania", role: "owner" }));
    expect(after.every((c) => c.passed)).toBe(true);
  });
});
