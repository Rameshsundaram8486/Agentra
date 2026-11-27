import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { decide } from "./actions";
import { approvalTurnaround, median, qaMetrics, reportCsv, REPORTS, turnaroundHours } from "./reports";
import { byId } from "./selectors";

describe("reports", () => {
  it("builds every report for the company and for one project, before and after the simulation runs", () => {
    for (const world of [createSeedWorld(), advance(createSeedWorld(), 40)]) {
      for (const report of REPORTS) {
        for (const projectId of ["all", "p-spo"]) {
          const body = report.build(world, projectId);
          expect(body.summary.length).toBeGreaterThan(0);
          for (const section of body.sections) for (const row of section.table?.rows ?? []) expect(row).toHaveLength(section.table!.columns.length);
        }
      }
    }
  });

  it("marks figures the records cannot support as placeholders", () => {
    expect(REPORTS.find((r) => r.id === "cost")!.build(createSeedWorld(), "all").placeholder).toMatch(/Placeholder/);
  });

  it("writes CSV with quoting", () => {
    const csv = reportCsv("Test", { summary: 'He said "hi", twice', figures: [{ label: "A", value: "1" }], sections: [{ heading: "T", table: { columns: ["x", "y"], rows: [["a,b", 2]] } }] });
    expect(csv.split("\r\n")).toEqual(["Test", '"He said ""hi"", twice"', "", "A,1", "", "T", "x,y", '"a,b",2']);
  });
});

describe("figures", () => {
  it("measures approval turnaround from raised to decided", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([])).toBeNull();
    const world = decide(createSeedWorld(), { decisionId: "d-cutover", action: "accept", personId: "u-rania", role: "owner" });
    expect(turnaroundHours(byId(world.decisions, "d-cutover")!)).toBe(26);
    expect(approvalTurnaround(world).decided.some((d) => d.decision.code === "DEC-006")).toBe(true);
  });

  it("computes the QA pass rate from executed cases", () => {
    const m = qaMetrics();
    expect(m.cases).toBe(412);
    expect([m.passed, m.executed, m.passRate]).toEqual([398, 406, 98]); // 6 performance cases are blocked, not executed
  });
});
