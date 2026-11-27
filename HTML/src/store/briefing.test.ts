import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { decide } from "./actions";
import { agentActivity, riskMatrix, taskTrend } from "./analytics";
import { briefing } from "./briefing";

describe("the Project Owner briefing", () => {
  it("is built from the records: what is critical, overdue, at risk and failed", () => {
    const brief = briefing(createSeedWorld());
    expect(brief.status).toBe("critical");
    expect(brief.headline).toBe("2 of 5 active projects need attention; 1 decision is overdue.");
    expect(brief.findings.map((f) => f.text)).toEqual(expect.arrayContaining([
      expect.stringContaining("SharePoint Online Migration is critical: RSK-001"),
      "DEC-006 is overdue: Move the cut-over date by one week",
      expect.stringContaining("Enterprise Intranet Modernization is at risk"),
      expect.stringContaining("INC-003 investigating"),
    ]));
    expect(brief.risks[0]!.code).toBe("RSK-001");
    expect(brief.escalations.map((d) => d.code)).toEqual(["DEC-006", "DEC-007"]);
    expect(brief.priorities[0]).toMatchObject({ rank: 1, link: "/decisions?id=d-cutover" });
  });

  it("labels corrective actions from incidents as hypotheses", () => {
    const action = briefing(createSeedWorld()).actions.find((a) => a.basis.startsWith("INC-003"));
    expect(action?.basis).toBe("INC-003 (hypothesis, medium confidence)");
  });

  it("changes when people decide", () => {
    const world = decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", personId: "u-rania", role: "owner" });
    const brief = briefing(world);
    expect(brief.findings.some((f) => f.text.includes("DEC-006"))).toBe(false);
    expect(brief.findings.some((f) => f.text.includes("is critical"))).toBe(false);
    expect(brief.headline).toBe("2 of 5 active projects need attention.");
    expect(brief.score).toBeGreaterThan(briefing(createSeedWorld()).score);
  });
});

describe("chart data", () => {
  it("counts completed tasks per day, ending today, and grows when the simulation completes work", () => {
    const before = taskTrend(createSeedWorld());
    expect(before).toHaveLength(14);
    expect(before.at(-1)!.day).toBe("2026-11-26");
    const after = taskTrend(advance(createSeedWorld(), 25));
    expect(after.at(-1)!.completed).toBeGreaterThan(before.at(-1)!.completed);
    expect(after.at(-1)!.total).toBe(before.at(-1)!.total + (after.at(-1)!.completed - before.at(-1)!.completed));
  });

  it("sums agent runs by category from the agents' records", () => {
    const rows = agentActivity(createSeedWorld());
    const world = createSeedWorld();
    expect(rows.reduce((s, r) => s + r.succeeded + r.failed, 0)).toBe(world.agents.reduce((s, a) => s + a.succeeded + a.failed, 0));
    expect(rows.reduce((s, r) => s + r.running, 0)).toBe(world.executions.filter((e) => e.status === "running").length);
  });

  it("places every open risk on the matrix once", () => {
    const codes = riskMatrix(createSeedWorld()).flatMap((c) => c.codes);
    expect(codes.sort()).toEqual(["RSK-001", "RSK-002", "RSK-003", "RSK-004", "RSK-005", "RSK-006"]);
  });
});
