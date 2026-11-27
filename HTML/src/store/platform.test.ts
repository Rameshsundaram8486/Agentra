import { describe, expect, it } from "vitest";
import { createSeedWorld } from "@/data/seed";
import { invariantProblems } from "@/test/invariants";
import { integrationCommand, setAutonomy, setNotification } from "./actions";
import { byId } from "./selectors";

const OWNER = ["u-rania", "owner"] as const;

describe("integrations", () => {
  it("lets the owner test and sync a connection, and records it", () => {
    const world = integrationCommand(createSeedWorld(), "spo", "sync", ...OWNER);
    expect(byId(world.integrations, "spo")!.lastSyncAt).toBe(world.now);
    expect(world.audit[0]).toMatchObject({ actor: "u-rania", action: "integration.sync", target: "SharePoint Online" });
    expect(invariantProblems(world)).toEqual([]);
  });

  it("refuses other roles, planned integrations and syncs that do not apply", () => {
    expect(() => integrationCommand(createSeedWorld(), "spo", "check", "u-omar", "project_manager")).toThrow(/Only the owner may test connections/);
    expect(() => integrationCommand(createSeedWorld(), "ollama", "check", ...OWNER)).toThrow(/Ollama \(local models\) is planned/);
    expect(() => integrationCommand(createSeedWorld(), "teams", "sync", ...OWNER)).toThrow(/has nothing to sync/);
  });

  it("never holds a credential", () => {
    const text = JSON.stringify(createSeedWorld().integrations);
    expect(text).not.toMatch(/sk-ant|secret=|password|-----BEGIN/i);
  });
});

describe("agent autonomy", () => {
  it("changes an action's level, versions the agent definition and audits the change", () => {
    const world = setAutonomy(createSeedWorld(), "developer", "ask_questions", "supervised", ...OWNER);
    expect(world.settings.autonomy["developer.ask_questions"]).toBe("supervised");
    expect(world.settings.configVersions.developer).toBe(3);
    expect(world.audit[0]!.detail).toBe('config/agents/developer/agent.yaml v2 → v3: "Ask questions about a work item" controlled → supervised');
  });

  it("keeps each action within its risk class and its preconditions", () => {
    expect(() => setAutonomy(createSeedWorld(), "uat_release", "invite_testers", "controlled", ...OWNER)).toThrow(/high-risk action; it may be at most supervised/);
    expect(() => setAutonomy(createSeedWorld(), "developer", "sandbox_build", "conditional", ...OWNER)).toThrow(/medium-risk action; it may be at most controlled/);
    expect(() => setAutonomy(createSeedWorld(), "developer", "ask_questions", "conditional", ...OWNER)).toThrow(/no approved precondition/);
    expect(() => setAutonomy(createSeedWorld(), "qa_tester", "retest_fixes", "supervised", "u-priya", "reviewer")).toThrow(/Only the owner may change agent autonomy/);
  });
});

describe("notification preferences", () => {
  it("are kept per role", () => {
    const world = setNotification(createSeedWorld(), "reviewer", "briefing.teams", true);
    expect(world.settings.notifications["reviewer.briefing.teams"]).toBe(true);
    expect(world.settings.notifications["owner.briefing.teams"]).toBe(false);
  });
});
