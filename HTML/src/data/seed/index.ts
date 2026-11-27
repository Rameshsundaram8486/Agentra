/* The starting state of the demo: one consistent world every screen reads from. */
import type { World } from "@/types";
import { AGENT_TYPES } from "../agentTypes";
import { at } from "../time";
import { ACTIVITY, ARTIFACTS, AUDIT, NOTIFICATIONS } from "./documents";
import { DECISIONS, INCIDENTS, RISKS } from "./governance";
import { defaultSettings, INTEGRATIONS } from "./platform";
import { CUSTOMERS, PEOPLE, PROJECTS } from "./projects";
import { AGENTS, EXECUTIONS, TASKS } from "./work";

export const WORLD_VERSION = 4; // bump when the shape or the seed changes, so saved demos restart from the seed

export function createSeedWorld(): World {
  // A deep copy, so resetting the demo never shares objects with a previous run.
  return structuredClone({
    version: WORLD_VERSION,
    seq: 1000,
    now: at(0),
    customers: CUSTOMERS,
    people: PEOPLE,
    projects: PROJECTS,
    agentTypes: AGENT_TYPES,
    agents: AGENTS,
    tasks: TASKS,
    executions: EXECUTIONS,
    decisions: DECISIONS,
    risks: RISKS,
    incidents: INCIDENTS,
    artifacts: ARTIFACTS,
    activity: ACTIVITY,
    notifications: NOTIFICATIONS,
    audit: AUDIT,
    integrations: INTEGRATIONS,
    settings: defaultSettings(),
    sim: { running: false, speed: 1, cursor: 0, done: [], elapsed: 0, lastEventAt: 0 },
  });
}
