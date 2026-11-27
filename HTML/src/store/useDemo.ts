/* The demo store: the world, the role the viewer acts in, the theme, and the commands. The world is saved in the
   browser so a refresh keeps the story; a version change or unreadable storage starts from the seed. */
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Autonomy, Role, World } from "@/types";
import { createSeedWorld, WORLD_VERSION } from "@/data/seed";
import { advance } from "@/simulation/engine";
import { controlExecution, decide, integrationCommand, markNotificationsRead, mutate, setAutonomy, setNotification, updateIncident, updateRisk, type DecisionInput, type IncidentCommand, type RiskCommand } from "./actions";
import { safeStorage } from "./safeStorage";

export type Theme = "dark" | "light";

/** The demo person each role is played by. */
export const ROLE_PEOPLE: Record<Role, string> = {
  owner: "u-rania",
  project_manager: "u-omar",
  reviewer: "u-priya",
  customer_approver: "u-daniel",
};

interface DemoState {
  world: World;
  role: Role;
  theme: Theme;
  setRole: (role: Role) => void;
  setTheme: (theme: Theme) => void;
  decide: (input: Omit<DecisionInput, "personId" | "role">) => void;
  controlExecution: (executionId: string, command: "pause" | "resume" | "retry") => void;
  markRead: (ids?: string[]) => void;
  updateIncident: (incidentId: string, command: IncidentCommand) => void;
  updateRisk: (riskId: string, command: RiskCommand) => void;
  integrationCommand: (integrationId: string, command: "check" | "sync") => void;
  setAutonomy: (typeKey: string, actionKey: string, level: Autonomy) => void;
  setNotification: (key: string, on: boolean) => void;
  startSimulation: () => void;
  pauseSimulation: () => void;
  setSpeed: (speed: World["sim"]["speed"]) => void;
  tick: () => void;
  reset: () => void;
}

export const useDemo = create<DemoState>()(
  persist(
    (set, get) => ({
      world: createSeedWorld(),
      role: "owner",
      theme: "dark",
      setRole: (role) => set({ role }),
      setTheme: (theme) => set({ theme }),
      decide: (input) => set({ world: decide(get().world, { ...input, role: get().role, personId: ROLE_PEOPLE[get().role] }) }),
      controlExecution: (executionId, command) =>
        set({ world: controlExecution(get().world, executionId, command, ROLE_PEOPLE[get().role], get().role) }),
      markRead: (ids) => set({ world: markNotificationsRead(get().world, ids) }),
      updateIncident: (incidentId, command) => set({ world: updateIncident(get().world, incidentId, command, ROLE_PEOPLE[get().role], get().role) }),
      updateRisk: (riskId, command) => set({ world: updateRisk(get().world, riskId, command, ROLE_PEOPLE[get().role], get().role) }),
      integrationCommand: (integrationId, command) => set({ world: integrationCommand(get().world, integrationId, command, ROLE_PEOPLE[get().role], get().role) }),
      setAutonomy: (typeKey, actionKey, level) => set({ world: setAutonomy(get().world, typeKey, actionKey, level, ROLE_PEOPLE[get().role], get().role) }),
      setNotification: (key, on) => set({ world: setNotification(get().world, get().role, key, on) }),
      startSimulation: () => set({ world: mutate(get().world, (w) => void (w.sim.running = true)) }),
      pauseSimulation: () => set({ world: mutate(get().world, (w) => void (w.sim.running = false)) }),
      setSpeed: (speed) => set({ world: mutate(get().world, (w) => void (w.sim.speed = speed)) }),
      tick: () => {
        const world = get().world;
        if (world.sim.running) set({ world: advance(world, world.sim.speed) });
      },
      reset: () => set({ world: createSeedWorld() }),
    }),
    {
      name: "agentra-command-center-demo",
      version: WORLD_VERSION,
      storage: createJSONStorage(() => safeStorage),
      partialize: (state) => ({ world: state.world, role: state.role, theme: state.theme }),
      migrate: () => ({ world: createSeedWorld(), role: "owner", theme: "dark" }) as Partial<DemoState>,
    },
  ),
);
