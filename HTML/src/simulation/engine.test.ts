import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { controlExecution, decide } from "@/store/actions";
import { byId } from "@/store/selectors";
import { invariantProblems } from "@/test/invariants";
import type { World } from "@/types";
import { advance, scenarioProgress } from "./engine";
import { REACTIONS, TIMELINE } from "./scenario";

function run(world: World, ticks: number, check = true): World {
  let current = world;
  for (let i = 0; i < ticks; i++) {
    current = advance(current);
    if (check) expect(invariantProblems(current), `after tick ${current.sim.elapsed}`).toEqual([]);
  }
  return current;
}

describe("the simulation", () => {
  it("keeps the world consistent on every tick, through the whole script", () => {
    const end = run(createSeedWorld(), 120);
    const progress = scenarioProgress(end);
    expect(progress.total).toBe(TIMELINE.length + REACTIONS.length);
    expect(TIMELINE.every((e) => end.sim.done.includes(e.id))).toBe(true); // the timeline ran to the end
    expect(progress.waiting).toBe(REACTIONS.length); // every reaction waits for a person
  });

  it("stays consistent when people make every decision as soon as they can", () => {
    const people = { owner: "u-rania", project_manager: "u-omar", reviewer: "u-priya", customer_approver: "u-daniel" } as const;
    let world = createSeedWorld();
    for (let tick = 0; tick < 160; tick++) {
      world = advance(world);
      for (const decision of world.decisions) {
        if (decision.status !== "pending" || decision.blockedBy) continue;
        const role = decision.allowedRoles[0]!;
        world = decide(world, { decisionId: decision.id, action: "accept", personId: people[role], role });
        expect(invariantProblems(world), `after deciding ${decision.code}`).toEqual([]);
      }
      expect(invariantProblems(world), `after tick ${world.sim.elapsed}`).toEqual([]);
    }
    expect(scenarioProgress(world).waiting).toBe(REACTIONS.filter((r) => r.alternative).length); // every reaction fired except those after a rejection
    expect(world.decisions.filter((d) => d.status === "pending")).toEqual([]);
    expect(byId(world.tasks, "t-s6")!.state).toBe("completed"); // the pilot migration ran
    expect(byId(world.projects, "p-spo")!.milestones.find((m) => m.title === "Pilot migration complete")!.done).toBe(true);
    expect(byId(world.tasks, "t-p6")!.state).toBe("completed"); // CR-002 applied
    expect(byId(world.tasks, "t-u6")!.state).toBe("completed"); // go-live checklist (Preview)
    expect(byId(world.risks, "r3")!.status).toBe("closed"); // DEF-014 fixed
  });

  it("revises a change set that was sent back, and the new version needs a new approval", () => {
    let world = run(createSeedWorld(), 9); // WI-004 v2 has passed its sandbox run
    world = decide(world, { decisionId: "d-wi004", action: "reject", comment: "Add a test for 1 million items", personId: "u-priya", role: "reviewer" });
    expect(byId(world.tasks, "t-s4")!.state).toBe("changes_requested");
    world = run(world, 10);
    const v3 = byId(world.decisions, "d-wi004-v3")!;
    expect(v3).toMatchObject({ code: "DEC-015", status: "pending" });
    expect(byId(world.artifacts, "doc-s-cs4")!.versions.at(-1)!.no).toBe(3);
    expect(v3.blockedBy).toBeDefined(); // waits for its own sandbox run
    world = run(world, 5);
    expect(byId(world.decisions, "d-wi004-v3")!.blockedBy).toBeUndefined();
    world = decide(world, { decisionId: "d-wi004-v3", action: "accept", personId: "u-priya", role: "reviewer" });
    expect(byId(world.decisions, "d-wi004-v3")!.outcome!.boundTo!.version).toBe(3);
    expect(byId(world.tasks, "t-s4")!.state).toBe("completed");
    expect(invariantProblems(world)).toEqual([]);
  });

  it("keeps the Project Owner Agent scanning after the script has run out", () => {
    const world = run(createSeedWorld(), 140, false);
    expect(world.activity.some((e) => e.text.startsWith("Project Owner Agent scan:"))).toBe(true);
  });

  it("is deterministic", () => {
    const a = run(createSeedWorld(), 60, false);
    const b = run(createSeedWorld(), 60, false);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });

  it("advances the simulated clock by 20 seconds a tick", () => {
    const world = createSeedWorld();
    expect(Date.parse(advance(world, 3).now) - Date.parse(world.now)).toBe(60_000);
  });

  it("never does work that waits for a human decision until that decision is made", () => {
    const untouched = run(createSeedWorld(), 120, false);
    expect(byId(untouched.tasks, "t-w2")!.state).toBe("waiting_for_input"); // DEC-001 not decided
    expect(byId(untouched.tasks, "t-i6")!.state).toBe("not_started"); // DEC-007 not decided

    let world = run(createSeedWorld(), 10, false);
    world = decide(world, { decisionId: "d-platform", action: "accept", personId: "u-rania", role: "owner" });
    world = run(world, 3);
    expect(byId(world.tasks, "t-w2")!.state).toBe("in_progress");
    world = run(world, 10);
    expect(byId(world.tasks, "t-w2")!.state).toBe("waiting_for_review");
    expect(byId(world.decisions, "d-brd")!.status).toBe("pending");
  });

  it("unblocks a change set approval only after its sandbox run passes", () => {
    let world = createSeedWorld();
    expect(byId(world.decisions, "d-wi004")!.blockedBy).toBeDefined();
    world = run(world, 8);
    expect(byId(world.decisions, "d-wi004")!.blockedBy).toBeUndefined();
    expect(byId(world.decisions, "d-wi004")!.evidence.at(-1)!.label).toContain("48 of 48 tests");
  });

  it("finishes a run a person retried, and the script then leaves that work alone", () => {
    let world = controlExecution(createSeedWorld(), "x-108", "retry", "u-omar", "project_manager");
    world = run(world, 9);
    expect(byId(world.executions, "x-108")!.status).toBe("succeeded");
    expect(byId(world.tasks, "t-i5")!.state).toBe("waiting_for_review");
    world = run(world, 60);
    expect(world.executions.some((e) => e.id === "x-302")).toBe(false); // the scripted rerun is no longer needed
  });

  it("does not finish a run a person paused", () => {
    let world = controlExecution(createSeedWorld(), "x-102", "pause", "u-omar", "project_manager");
    world = run(world, 60);
    expect(byId(world.executions, "x-102")!.status).toBe("paused");
    expect(byId(world.tasks, "t-i1")!.state).toBe("in_progress");
  });
});
