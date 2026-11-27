import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { decide } from "@/store/actions";
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

describe("Projects", () => {
  it("filters the portfolio and switches between table, cards and kanban", async () => {
    await go("#/projects", "Projects");
    expect(screen.getAllByRole("row")).toHaveLength(8); // 7 projects and the header
    fireEvent.change(screen.getByRole("combobox", { name: "Health" }), { target: { value: "critical" } });
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getByRole("row", { name: /SharePoint Online Migration/ })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Health" }), { target: { value: "all" } });
    fireEvent.click(screen.getByRole("radio", { name: /Kanban/ }));
    expect(within(screen.getByRole("region", { name: "Development" })).getByText("SharePoint Online Migration")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Pre-sales" })).getByText("Azure AI Document Processing")).toBeInTheDocument();
  });
});

describe("the Project Workspace", () => {
  it("shows the header and switches between its 13 tabs", async () => {
    await go("#/projects/p-spo", "SharePoint Online Migration");
    expect(screen.getByRole("region", { name: "Project summary" })).toHaveTextContent("Omar Siddiqui");
    expect(screen.getAllByRole("tab")).toHaveLength(13);
    expect(screen.getByText(/Critical: RSK-001/)).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("tab", { name: /Development/ }));
    fireEvent.click(screen.getByRole("tab", { name: /Development/ }));
    expect(await screen.findByText("Large-list migration handler (lists over 5,000 items)", { exact: false })).toBeInTheDocument();
    expect(window.location.hash).toContain("tab=development");
  });
});

describe("the lifecycle and phase workspaces", () => {
  it("shows the 13 phases with their gates, for the portfolio and for one project", async () => {
    await go("#/lifecycle", "Delivery Lifecycle");
    const rail = screen.getByRole("list", { name: "Delivery lifecycle" });
    expect(within(rail).getAllByRole("button")).toHaveLength(13);
    fireEvent.click(within(rail).getByRole("button", { name: /^Phase 11, Customer UAT and Sign-Off/ }));
    const [phasePanel, uatView] = screen.getAllByRole("region", { name: /Phase 11: Customer UAT and Sign-Off/ });
    expect(phasePanel).toHaveTextContent("Customer approver; never an agent");
    expect(uatView).toHaveTextContent("UAT progress by area"); // the project in Phase 11 now
    fireEvent.change(screen.getByRole("combobox", { name: "Show the lifecycle for" }), { target: { value: "p-ess" } });
    expect(within(screen.getByRole("list", { name: "Delivery lifecycle" })).getAllByRole("button", { name: /Completed/ })).toHaveLength(13);
  });

  it("derives live statuses: an answered decision confirms requirements", async () => {
    act(() => useDemo.setState({ world: decide(createSeedWorld(), { decisionId: "d-approval-chain", action: "accept", personId: "u-rania", role: "owner" }) }));
    await go("#/delivery/requirements", "Requirements");
    const item = screen.getByText("Requests above AED 10,000 route to the general manager and group finance").closest("li")!;
    expect(item).toHaveTextContent("confirmed");
  });

  it("shows a change set's build as passed once its sandbox run passes", async () => {
    act(() => useDemo.setState({ world: advance(createSeedWorld(), 9) }));
    await go("#/delivery/development", "Development");
    expect(screen.getByRole("row", { name: /WI-004/ })).toHaveTextContent("Passed");
  });

  it("meets the QA exit criteria for critical defects only after DEF-014 is fixed", async () => {
    await go("#/delivery/qa", "QA and Testing");
    expect(screen.getByText("No open critical defects").closest("li")!.querySelector("[aria-label]")).toHaveAttribute("aria-label", "Not met");
  });

  it("marks phases outside the MVP as previews", async () => {
    await go("#/business/proposals", "Proposals and Estimates");
    expect(screen.getByText(/Preview: this phase is outside the MVP/)).toBeInTheDocument();
    expect(screen.getByText("Azure AI Document Processing", { selector: "td" })).toBeInTheDocument();
  });
});
