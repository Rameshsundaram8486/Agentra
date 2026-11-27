import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
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

describe("the Knowledge Base", () => {
  it("previews a document with its versions, approvals and traceability", async () => {
    await go("#/knowledge?doc=doc-s-cs4", "Knowledge Base");
    const preview = screen.getByRole("article", { name: "Change set WI-004 preview" });
    expect(preview).toHaveTextContent("Source code (change set)");
    expect(preview).toHaveTextContent("v1");
    expect(preview).toHaveTextContent("DEC-005");
    expect(within(preview).getByRole("list", { name: "Documents sharing these references" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Type" }), { target: { value: "test_plan" } });
    expect(within(screen.getByRole("list", { name: "Documents" })).getAllByRole("button")).toHaveLength(1);
  });
});

describe("Integrations and the Model Gateway", () => {
  it("tests a connection as the owner and refuses other roles", async () => {
    await go("#/admin/integrations", "Integrations");
    const azure = screen.getByRole("article", { name: "Azure" });
    fireEvent.click(within(azure).getByRole("button", { name: "Test connection" }));
    expect(within(azure).getByRole("status")).toHaveTextContent("Certificate expires in 12 days");
    expect(within(screen.getByRole("article", { name: "Ollama (local models)" })).queryByRole("button")).not.toBeInTheDocument();
    act(() => useDemo.setState({ role: "reviewer" }));
    fireEvent.click(within(screen.getByRole("article", { name: "SharePoint Online" })).getByRole("button", { name: "Sync now" }));
    expect(within(screen.getByRole("article", { name: "SharePoint Online" })).getByRole("alert")).toHaveTextContent("Only the owner may start a sync");
  });

  it("shows routing, usage and the cap, and never a key", async () => {
    await go("#/admin/model-gateway", "Model Gateway");
    expect(screen.getByRole("region", { name: "Monthly cap" })).toHaveTextContent("$50.00");
    expect(screen.getByText(/API key: stored in the secrets vault/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Routing/ })).toHaveTextContent("Business Analyst Agent");
    expect(document.body.textContent).not.toMatch(/sk-ant/);
  });
});

describe("Settings and governance", () => {
  it("changes an action's autonomy within its risk class", async () => {
    await go("#/admin/agents?agent=qa_tester", "Agent Configuration");
    fireEvent.change(screen.getByRole("combobox", { name: "Autonomy for Retest a fixed defect" }), { target: { value: "supervised" } });
    expect(screen.getByRole("status")).toHaveTextContent('"Retest a fixed defect" is now supervised');
    expect(screen.getByRole("region", { name: "Configuration history" })).toHaveTextContent("v1 → v2");
    fireEvent.change(screen.getByRole("combobox", { name: "Autonomy for Run approved test suites in sandbox VMs" }), { target: { value: "conditional" } });
    expect(screen.getByRole("alert")).toHaveTextContent("medium-risk action; it may be at most controlled");
    expect(screen.getByText("Never: people only. Not configurable.")).toBeInTheDocument();
  });

  it("shows the phase workflows and approval policies from config", async () => {
    await go("#/admin/workflows", "Workflow Configuration");
    expect(screen.getByText("phase_09_development_and_implementation.yaml · v2")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Approval policies/ })).toHaveTextContent("UAT sign-off record");
  });

  it("switches the demo person from the user list and shows the permission matrix", async () => {
    await go("#/admin/users", "Users and Permissions");
    fireEvent.click(screen.getByRole("button", { name: "Act as Priya" }));
    expect(useDemo.getState().role).toBe("reviewer");
    expect(screen.getByRole("row", { name: /Verify and close incidents/ })).toBeInTheDocument();
  });

  it("saves notification preferences and filters the audit log", async () => {
    await go("#/admin/settings", "System Settings");
    const teams = screen.getByRole("checkbox", { name: "Daily Project Owner briefing: Teams" });
    expect(teams).not.toBeChecked();
    fireEvent.click(teams);
    expect(useDemo.getState().world.settings.notifications["owner.briefing.teams"]).toBe(true);
    fireEvent.change(screen.getByRole("combobox", { name: "Actor" }), { target: { value: "agents" } });
    expect(screen.getAllByRole("row").slice(1).every((r) => !/Rania|Omar|Priya|Sara|Daniel/.test(r.textContent ?? ""))).toBe(true);
  });
});
