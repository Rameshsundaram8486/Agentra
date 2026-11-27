import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
import { advance } from "@/simulation/engine";
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

const review = () => screen.getByRole("dialog");

/** Opens a decision's review panel by its link; the panel is modal, so the page behind it is hidden from queries. */
async function openReview(id: string) {
  window.location.hash = `#/decisions?id=${id}`;
  render(<App />);
  return screen.findByRole("dialog", {}, { timeout: 5000 });
}

describe("the Decision Center", () => {
  it("shows the queues and filters the cards", async () => {
    await go("#/decisions", "Decision Center");
    expect(screen.getAllByRole("button", { name: /^DEC-\d+ / })).toHaveLength(9); // pending
    fireEvent.click(screen.getByRole("button", { name: /^Overdue/ }));
    expect(screen.getAllByRole("button", { name: /^DEC-\d+ / }).map((b) => b.getAttribute("aria-label"))).toEqual(["DEC-006 Move the cut-over date by one week"]);
    fireEvent.click(screen.getByRole("button", { name: /^All decisions/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Kind" }), { target: { value: "escalation" } });
    expect(screen.getAllByRole("button", { name: /^DEC-\d+ / })).toHaveLength(2);
  });

  it("records a different option with constraints, keeping the AI recommendation beside it", async () => {
    await openReview("d-platform");
    fireEvent.click(within(review()).getByRole("radio", { name: /^Hybrid/ }));
    fireEvent.change(within(review()).getByRole("textbox", { name: /Constraints/ }), { target: { value: "Purchase orders above AED 50,000 stay on premises" } });
    fireEvent.click(within(review()).getByRole("button", { name: "Use the selected option" }));
    expect(within(review()).getByRole("status")).toHaveTextContent("Recorded your choice");
    expect(within(review()).getByRole("region", { name: "Original AI recommendation" })).toHaveTextContent("SharePoint Online with Power Automate");
    const final = within(review()).getByRole("region", { name: "Final human decision" });
    expect(final).toHaveTextContent("Hybrid");
    expect(final).toHaveTextContent("Purchase orders above AED 50,000 stay on premises");
    expect(within(review()).getAllByText('Chose "Hybrid" instead of the recommendation')).toHaveLength(2); // history and audit trail
    expect(byId(useDemo.getState().world.decisions, "d-platform")!.status).toBe("modified");
  });

  it("enters a custom option", async () => {
    await openReview("d-platform");
    fireEvent.click(within(review()).getByRole("radio", { name: /Other: my own option/ }));
    fireEvent.change(within(review()).getByRole("textbox", { name: "Your own option" }), { target: { value: "Power Apps on Dataverse" } });
    fireEvent.click(within(review()).getByRole("button", { name: "Use my own option" }));
    expect(within(review()).getByRole("region", { name: "Final human decision" })).toHaveTextContent("Power Apps on Dataverse");
  });

  it("explains who may decide and lets the viewer switch to that role", async () => {
    act(() => useDemo.setState({ role: "project_manager" }));
    await openReview("d-cutover");
    fireEvent.click(within(review()).getByRole("button", { name: "Accept recommendation" }));
    expect(within(review()).getByRole("alert")).toHaveTextContent("Only owner may decide DEC-006; you are acting as project manager");
    fireEvent.click(within(review()).getByRole("button", { name: "Act as owner" }));
    fireEvent.click(within(review()).getByRole("button", { name: "Accept recommendation" }));
    expect(within(review()).getByRole("region", { name: "Final human decision" })).toHaveTextContent("Move cut-over to 24 December");
    expect(within(review()).getByText("Cut-over moved to 24 December; RSK-001 now mitigated")).toBeInTheDocument(); // what it changed
  });

  it("shows the history and audit trail", async () => {
    await openReview("d-tool");
    expect(within(review()).getByText("Chose SPMT for content with a ShareGate trial for the permission report")).toBeInTheDocument();
    expect(within(review()).getByRole("table")).toHaveTextContent("decision.outcome");
    expect(within(review()).queryByRole("button", { name: "Accept recommendation" })).not.toBeInTheDocument(); // already decided
  });
});

describe("the Approval Inbox", () => {
  it("holds a change set until its tests pass, then binds the approval to the version", async () => {
    act(() => useDemo.setState({ role: "reviewer" }));
    await go("#/approvals", "Approval Inbox");
    expect(within(screen.getByRole("region", { name: /Waiting for evidence/ })).getByText(/Approve change set WI-004 v2/)).toBeInTheDocument();
    act(() => useDemo.setState({ world: advance(useDemo.getState().world, 9) }));
    fireEvent.click(within(screen.getByRole("region", { name: /Ready for your decision/ })).getByRole("button", { name: /WI-004 v2/ }));
    fireEvent.click(within(review()).getByRole("button", { name: "Approve" }));
    expect(within(review()).getByRole("region", { name: "Final human decision" })).toHaveTextContent(/Bound to Change set WI-004 v2, sha256/);
    fireEvent.keyDown(review(), { key: "Escape" });
    expect(within(screen.getByRole("region", { name: /Decided approvals/ })).getByText(/Approve change set WI-004 v2/)).toBeInTheDocument();
  });
});

describe("Recommendations and Escalations", () => {
  it("compares what the agent recommended with what people decided", async () => {
    await go("#/recommendations", "Recommendations");
    const row = screen.getByRole("row", { name: /DEC-010/ });
    expect(row).toHaveTextContent("ShareGate");
    expect(row).toHaveTextContent("Microsoft SPMT for content");
  });

  it("lists open escalations with what is at stake", async () => {
    await go("#/escalations", "Escalations");
    const cutover = screen.getByRole("article", { name: /DEC-006/ });
    expect(cutover).toHaveTextContent("RSK-001 open");
    expect(cutover).toHaveTextContent("INC-003 investigating");
    expect(screen.getByRole("article", { name: /DEC-007/ })).toBeInTheDocument();
  });
});
