import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
import { byId } from "@/store/selectors";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

beforeEach(() => {
  useDemo.setState({ world: createSeedWorld(), role: "owner", theme: "dark" });
  useUi.setState({ sidebarCollapsed: false, foldedGroups: [], mobileNavOpen: false, paletteOpen: false });
});

async function go(hash: string, heading: string) {
  window.location.hash = hash;
  render(<App />);
  return screen.findByRole("heading", { level: 1, name: heading }, { timeout: 5000 });
}

describe("the Project Owner Agent", () => {
  it("monitors the company and opens an incident's root-cause analysis from a link", async () => {
    await go("#/owner?incident=inc-3", "Project Owner Agent");
    expect(screen.getByRole("region", { name: "Failed agent executions" })).toHaveTextContent("Dry run: throttling-aware batch scheduler");
    expect(screen.getByRole("region", { name: "Overdue decisions" })).toHaveTextContent("DEC-006");
    const cause = screen.getByRole("region", { name: "Probable cause" });
    expect(cause).toHaveTextContent("AI hypothesis, medium confidence");
    expect(screen.getByRole("region", { name: "Observed evidence" })).toHaveTextContent("Confirmed facts");
  });

  it("lets a project manager confirm the cause, and refuses a reviewer", async () => {
    act(() => useDemo.setState({ role: "reviewer" }));
    await go("#/owner?incident=inc-3", "Project Owner Agent");
    fireEvent.click(screen.getByRole("button", { name: "Confirm the cause" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Only an owner or a project manager may update incidents");
    act(() => useDemo.setState({ role: "project_manager" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm the cause" }));
    expect(screen.getByRole("region", { name: "Probable cause" })).toHaveTextContent("Confirmed by Omar Siddiqui");
    fireEvent.click(screen.getByRole("button", { name: "Mark resolved" }));
    fireEvent.click(screen.getByRole("button", { name: "Verify and close" }));
    expect(byId(useDemo.getState().world.incidents, "inc-3")!.status).toBe("closed");
  });
});

describe("Project Health and Risk and Compliance", () => {
  it("shows the records behind a project's health", async () => {
    await go("#/health?project=p-spo", "Project Health");
    expect(screen.getByRole("region", { name: "Health signals" })).toHaveTextContent("RSK-001");
    fireEvent.click(within(screen.getByRole("list", { name: "Projects" })).getByRole("button", { name: /Power Platform Automation/ }));
    expect(window.location.hash).toContain("project=p-power");
  });

  it("updates a risk from the register and runs the governance checks", async () => {
    await go("#/risk", "Risk and Compliance");
    expect(screen.getByRole("region", { name: "Governance checks" })).toHaveTextContent("No decision is past its deadline");
    fireEvent.click(screen.getByRole("row", { name: /RSK-003/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start mitigating" }));
    expect(byId(useDemo.getState().world.risks, "r3")!.status).toBe("mitigating");
  });
});

describe("performance and reports", () => {
  it("shows company and agent performance with drill-down", async () => {
    await go("#/performance", "Company Performance");
    fireEvent.click(screen.getByRole("row", { name: /SharePoint Online Migration/ }));
    expect(window.location.hash).toBe("#/projects/p-spo");
  });

  it("lists agents by success rate", async () => {
    await go("#/agents/performance", "Agent Performance");
    expect(screen.getByRole("list", { name: "Success rate by agent" })).toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeGreaterThan(20);
  });

  it("previews a report, filters it by project and exports it", async () => {
    await go("#/reports?report=risks", "Reports and Analytics");
    const preview = () => screen.getByRole("article", { name: "Project risk analysis preview" });
    expect(preview()).toHaveTextContent("RSK-006");
    fireEvent.change(screen.getByRole("combobox", { name: "Project" }), { target: { value: "p-spo" } });
    expect(preview()).not.toHaveTextContent("RSK-006");
    expect(preview()).toHaveTextContent("RSK-001");
    let blob: Blob | undefined;
    Object.assign(URL, { createObjectURL: (b: Blob) => { blob = b; return "blob:report"; }, revokeObjectURL: () => {} });
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    expect(screen.getByRole("status")).toHaveTextContent(/Downloaded agentra-risks-2026-11-26\.csv/);
    expect(await blob!.text()).toContain("RSK-001");
    fireEvent.click(within(screen.getByRole("list", { name: "Report catalogue" })).getByRole("button", { name: /Cost and utilization/ }));
    expect(screen.getByRole("article", { name: "Cost and utilization preview" })).toHaveTextContent("Placeholder");
  });
});
