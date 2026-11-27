import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

beforeEach(() => {
  useDemo.setState({ world: createSeedWorld(), role: "owner", theme: "dark" });
  useUi.setState({ sidebarCollapsed: false, foldedGroups: [], mobileNavOpen: false, paletteOpen: false });
  window.location.hash = "#/";
});

describe("the Executive Command Center", () => {
  it("shows the key figures from the records", () => {
    render(<App />);
    const figures = screen.getByRole("region", { name: "Key figures" });
    expect(within(figures).getByRole("button", { name: /Active projects\s*5/ })).toBeInTheDocument();
    expect(within(figures).getByRole("button", { name: /Pending human decisions\s*9\s*1 overdue/ })).toBeInTheDocument();
    expect(within(figures).getByRole("button", { name: /Projects at risk\s*2/ })).toBeInTheDocument();
  });

  it("shows the Project Owner briefing and opens the full briefing, separating facts from recommendations", () => {
    render(<App />);
    const brief = screen.getByRole("region", { name: "Project Owner Intelligence Briefing" });
    expect(within(brief).getByText("2 of 5 active projects need attention; 1 decision is overdue.")).toBeInTheDocument();
    expect(within(brief).getByRole("img", { name: /Company health score \d+ of 100: Needs action/ })).toBeInTheDocument();
    fireEvent.click(within(brief).getByRole("button", { name: "Open full briefing" }));
    const drawer = screen.getByRole("dialog", { name: "Project Owner Intelligence Briefing" });
    for (const section of ["Important findings", "Risks detected", "Recommended actions", "Pending escalations", "Recommended priorities"]) {
      expect(within(drawer).getByRole("heading", { name: section })).toBeInTheDocument();
    }
    expect(within(drawer).getAllByText("From records").length).toBe(2);
    expect(within(drawer).getAllByText("AI recommendation").length).toBe(2);
    expect(within(drawer).getByText(/INC-003 \(hypothesis, medium confidence\)/)).toBeInTheDocument();
  });

  it("lists decisions needing people, overdue first, and marks the ones the viewer can make", () => {
    render(<App />);
    const attention = screen.getByRole("region", { name: /Human attention required/ });
    const items = within(attention).getAllByRole("link").filter((a) => a.getAttribute("href")?.startsWith("#/decisions?id="));
    expect(items[0]).toHaveTextContent("Move the cut-over date by one week");
    expect(items[0]).toHaveTextContent("overdue");
    expect(items[0]).toHaveTextContent("You can decide");
  });

  it("updates when a person decides: the overdue escalation leaves the briefing and the project is no longer critical", () => {
    render(<App />);
    act(() => useDemo.getState().decide({ decisionId: "d-cutover", action: "accept" }));
    const brief = screen.getByRole("region", { name: "Project Owner Intelligence Briefing" });
    expect(within(brief).getByText("2 of 5 active projects need attention.")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Key figures" })).getByRole("button", { name: /Pending human decisions\s*8\s*none overdue/ })).toBeInTheDocument();
    expect(screen.getAllByText(/Rania Al Mansoori chose "Move cut-over to 24 December"/).length).toBeGreaterThan(0);
  });

  it("updates as the simulation runs", () => {
    render(<App />);
    act(() => {
      useDemo.getState().startSimulation();
      for (let i = 0; i < 16; i++) useDemo.getState().tick(); // regression run 3 finishes at tick 14
    });
    expect(screen.getAllByText(/QA Agent finished regression run 3/).length).toBeGreaterThan(0);
  });
});
