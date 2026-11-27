import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { decide } from "./actions";
import { decisionEffects, humanChoice, inQueue, linkedRecords, recommendationStats, type DecisionQueue } from "./decisions";
import { byId } from "./selectors";

const count = (queue: DecisionQueue, world = createSeedWorld()) => world.decisions.filter((d) => inQueue(world, d, queue)).map((d) => d.code).sort();

describe("decision queues", () => {
  it("sorts the seed decisions into pending, high priority, overdue, approved, rejected and deferred", () => {
    expect(count("pending")).toHaveLength(9);
    expect(count("high")).toEqual(["DEC-001", "DEC-003", "DEC-004", "DEC-005", "DEC-006", "DEC-007", "DEC-008"]);
    expect(count("overdue")).toEqual(["DEC-006"]);
    expect(count("approved")).toEqual(["DEC-010"]);
    expect(count("rejected")).toEqual(["DEC-012"]);
    expect(count("deferred")).toEqual(["DEC-011"]);
  });

  it("moves a decision between queues when a person decides it", () => {
    const world = decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", personId: "u-rania", role: "owner" });
    expect(count("overdue", world)).toEqual([]);
    expect(count("approved", world)).toEqual(["DEC-006", "DEC-010"]);
  });
});

describe("recommendations against human decisions", () => {
  it("counts what people kept, changed, rejected and deferred", () => {
    const stats = recommendationStats(createSeedWorld().decisions.filter((d) => d.kind !== "approval"));
    expect(stats).toMatchObject({ asRecommended: 0, changed: 1, rejected: 1, deferred: 1, agreement: 0 });
    expect(humanChoice(byId(createSeedWorld().decisions, "d-tool")!)).toBe("Microsoft SPMT for content, ShareGate trial only for the permission report");
  });
});

describe("linked records and effects", () => {
  it("links an escalation to the risk and incident it refers to, as they are now", () => {
    const links = linkedRecords(createSeedWorld(), byId(createSeedWorld().decisions, "d-cutover")!);
    expect(links.risks.map((r) => r.code)).toEqual(["RSK-001"]);
    expect(links.incidents.map((i) => i.code)).toEqual(["INC-003"]);
    expect(linkedRecords(createSeedWorld(), byId(createSeedWorld().decisions, "d-def014")!).risks.map((r) => r.code)).toEqual(["RSK-003"]);
  });

  it("lists what a decision changed", () => {
    const world = decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", personId: "u-rania", role: "owner" });
    const effects = decisionEffects(world, byId(world.decisions, "d-cutover")!).map((e) => e.text);
    expect(effects).toEqual([expect.stringContaining("Rania Al Mansoori chose \"Move cut-over to 24 December\""), "Cut-over moved to 24 December; RSK-001 now mitigated"]);
  });
});
