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

function go(hash: string) {
  window.location.hash = hash;
  render(<App />);
}

describe("Live Operations", () => {
  it("shows runs in flight, queues and people dependencies from the records", async () => {
    go("#/operations");
    const figures = await screen.findByRole("region", { name: "Operational figures" }, { timeout: 5000 });
    expect(within(figures).getByText("Runs in flight").parentElement?.parentElement).toHaveTextContent("5");
    expect(within(figures).getByText("Waiting on people").parentElement?.parentElement).toHaveTextContent("5"); // 4 reviews or answers, and CR-002 waiting for DEC-003
    expect(screen.getByRole("figure", { name: /Delivery pipeline/ })).toBeInTheDocument();
  });

  it("opens a run with its logs, refuses pause for a reviewer and allows it for a project manager", async () => {
    act(() => useDemo.getState().setRole("reviewer"));
    go("#/operations?run=x-101");
    const drawer = await screen.findByRole("dialog", { name: "Implement WI-005: managed metadata mapping" }, { timeout: 5000 });
    expect(within(drawer).getByRole("log")).toHaveTextContent("Mapping 2,140 terms to 9 term sets");
    fireEvent.click(within(drawer).getByRole("button", { name: "Pause" }));
    expect(within(drawer).getByRole("alert")).toHaveTextContent("Only an owner or a project manager may pause agent runs; you are acting as reviewer");
    expect(byId(useDemo.getState().world.executions, "x-101")!.status).toBe("running");

    act(() => useDemo.getState().setRole("project_manager"));
    fireEvent.click(within(drawer).getByRole("button", { name: "Pause" }));
    expect(byId(useDemo.getState().world.executions, "x-101")!.status).toBe("paused");
    expect(within(drawer).getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });
});

describe("the Agent Control Center", () => {
  it("filters agents by status and search, and opens an agent's profile with its permissions", async () => {
    go("#/agents");
    await screen.findByRole("heading", { level: 1, name: "Agent Control Center" }, { timeout: 5000 });
    fireEvent.click(screen.getByRole("button", { name: /^Blocked 2$/ }));
    const cards = () => screen.getAllByRole("button").filter((b) => b.className.includes("radius-panel"));
    expect(cards().map((c) => c.textContent)).toEqual([expect.stringContaining("QA Agent 2"), expect.stringContaining("Commercial Control Agent")]);
    fireEvent.click(screen.getByRole("button", { name: /^Blocked 2$/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Search agents" }), { target: { value: "security" } });
    fireEvent.click(cards()[0]!);
    const profile = await screen.findByRole("dialog", { name: "Security Reviewer Agent" });
    expect(within(profile).getByText("Design read")).toBeInTheDocument();
    expect(within(profile).getByText(/Agents never approve or record decisions/)).toBeInTheDocument();
  });

  it("lists every agent in the directory", async () => {
    go("#/agents/directory");
    await screen.findByRole("heading", { level: 1, name: "Agent Directory" }, { timeout: 5000 });
    expect(screen.getAllByRole("row")).toHaveLength(useDemo.getState().world.agents.length + 1);
  });
});
