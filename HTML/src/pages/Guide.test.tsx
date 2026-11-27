import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/app/App";
import { createSeedWorld } from "@/data/seed";
import { GUIDE_STEPS } from "@/data/presenterGuide";
import { useDemo } from "@/store/useDemo";
import { useUi } from "@/store/useUi";

beforeEach(() => {
  useDemo.setState({ world: createSeedWorld(), role: "owner", theme: "dark" });
  useUi.setState({ sidebarCollapsed: false, foldedGroups: [], mobileNavOpen: false, paletteOpen: false });
});

describe("the presenter guide", () => {
  it("opens every step's screen with the step's role", async () => {
    for (const [i, step] of GUIDE_STEPS.entries()) {
      window.location.hash = "#/guide";
      render(<App />);
      await screen.findByRole("heading", { level: 1, name: "Presenter guide" }, { timeout: 15_000 });
      const item = screen.getByRole("listitem", { name: `Step ${i + 1}: ${step.title}` });
      fireEvent.click(within(item).getByRole("button", { name: /^Open/ }));
      expect(window.location.hash).toBe(`#${step.link}`);
      if (step.role) expect(useDemo.getState().role).toBe(step.role);
      // A real page or a decision's review panel opens, never "This page does not exist".
      await screen.findAllByRole(step.link.includes("?id=") ? "dialog" : "heading", {}, { timeout: 15_000 });
      expect(screen.queryByText("This page does not exist")).not.toBeInTheDocument();
      cleanup();
    }
  }, 180_000);
});
