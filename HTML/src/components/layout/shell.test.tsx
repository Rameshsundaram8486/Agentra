import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { NAV_ITEMS, NAVIGATION } from "@/app/navigation";
import { createSeedWorld } from "@/data/seed";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

// Pages built so far; the rest show their placeholder.
const BUILT = [
  "command", "operations", "agents", "directory", "history", "projects", "pipeline", "board", "milestones", "lifecycle",
  "requirements", "architecture", "development", "qa", "uat", "releases", "sales", "discovery", "proposals", "commercial",
  "decisions", "approvals", "recommendations", "escalations", "owner", "health", "risk", "performance", "agent-performance", "reports",
  "knowledge", "integrations", "gateway", "agent-config", "workflow-config", "users", "settings",
];

beforeEach(() => {
  useDemo.setState({ world: createSeedWorld(), role: "owner", theme: "dark" });
  useUi.setState({ sidebarCollapsed: false, foldedGroups: [], mobileNavOpen: false, paletteOpen: false });
  window.location.hash = "#/";
});

function sidebar() {
  return screen.getAllByRole("navigation", { name: "Main" })[0]!;
}

describe("the application shell", () => {
  it("lists every group and item in the sidebar", () => {
    render(<App />);
    const nav = sidebar();
    for (const group of NAVIGATION) expect(within(nav).getByRole("button", { name: group.label })).toBeInTheDocument();
    for (const item of NAV_ITEMS) expect(within(nav).getByRole("link", { name: new RegExp(item.label) })).toBeInTheDocument();
  });

  it("opens a real page for every navigation item, with its title, and highlights it", async () => {
    render(<App />);
    for (const item of NAV_ITEMS) {
      const link = within(sidebar()).getByRole("link", { name: new RegExp(`^${item.label}`) });
      fireEvent.click(link);
      // Pages load on first use; under a full parallel test run the first load of a page bundle can take a while.
      expect(await screen.findByRole("heading", { level: 1, name: item.label }, { timeout: 15_000 })).toBeInTheDocument();
      if (!BUILT.includes(item.id)) expect(screen.getAllByText(`Arrives in Stage ${item.stage}`).length).toBeGreaterThan(0);
      expect(within(sidebar()).getByRole("link", { name: new RegExp(`^${item.label}`) })).toHaveAttribute("aria-current", "page");
      expect(within(sidebar()).getAllByRole("link", { current: "page" })).toHaveLength(1); // a parent path is not highlighted with its child
    }
  }, 180_000); // renders all 33 pages

  it("marks pages outside the MVP as previews", () => {
    render(<App />);
    fireEvent.click(within(sidebar()).getByRole("link", { name: /^Sales and Leads/ }));
    expect(screen.getByText("Preview, not in the MVP")).toBeInTheDocument();
  });

  it("folds a group and collapses the sidebar to icons", () => {
    render(<App />);
    const nav = sidebar();
    fireEvent.click(within(nav).getByRole("button", { name: "Administration" }));
    expect(within(nav).queryByRole("link", { name: /Model Gateway/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Collapse the sidebar" }));
    expect(useUi.getState().sidebarCollapsed).toBe(true);
    expect(within(sidebar()).queryByText("Executive Command Center")).not.toBeInTheDocument(); // icons only
  });

  it("counts the decisions the viewer's role can make, the same in the top bar and the sidebar", () => {
    render(<App />);
    const forOwner = useDemo.getState().world.decisions.filter((d) => d.status === "pending" && d.allowedRoles.includes("owner")).length;
    expect(screen.getByRole("button", { name: `Decisions waiting for you: ${forOwner}` })).toBeInTheDocument();
    expect(within(sidebar()).getByRole("link", { name: new RegExp(`^Decision Center${forOwner} decisions you can make`) })).toBeInTheDocument();
    act(() => useDemo.getState().setRole("customer_approver"));
    expect(screen.getByRole("button", { name: "Decisions waiting for you: 1" })).toBeInTheDocument();
  });

  it("searches records with Ctrl+K and opens the result", () => {
    render(<App />);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const input = screen.getByRole("textbox", { name: "Search" });
    fireEvent.change(input, { target: { value: "WI-004" } });
    expect(screen.getByRole("option", { name: /DEC-005 Approve change set WI-004 v2/ })).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(window.location.hash).toBe("#/decisions?id=d-wi004");
  });

  it("shows the unread notification count", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "Notifications: 4 unread" })).toBeInTheDocument();
  });
});
