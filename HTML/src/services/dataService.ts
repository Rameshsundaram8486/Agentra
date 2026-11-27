/* The boundary between screens and data. Screens read the world through hooks and send commands through a
   DataService. Today the only implementation is the simulated demo; an API-backed implementation can later map
   these calls to the Agentra FastAPI endpoints (projects, phases, decisions, agent runs, implementation, reports)
   without changing any screen. */
import type { DecisionInput, IncidentCommand, RiskCommand } from "@/store/actions";
import { useDemo } from "@/store/useDemo";
import type { Autonomy } from "@/types";

export interface DataService {
  readonly mode: "demo" | "api";
  decide(input: Omit<DecisionInput, "personId" | "role">): void;
  controlExecution(executionId: string, command: "pause" | "resume" | "retry"): void;
  markNotificationsRead(ids?: string[]): void;
  updateIncident(incidentId: string, command: IncidentCommand): void;
  updateRisk(riskId: string, command: RiskCommand): void;
  integrationCommand(integrationId: string, command: "check" | "sync"): void;
  setAutonomy(typeKey: string, actionKey: string, level: Autonomy): void;
  setNotification(key: string, on: boolean): void;
}

export const demoDataService: DataService = {
  mode: "demo",
  decide: (input) => useDemo.getState().decide(input),
  controlExecution: (executionId, command) => useDemo.getState().controlExecution(executionId, command),
  markNotificationsRead: (ids) => useDemo.getState().markRead(ids),
  updateIncident: (incidentId, command) => useDemo.getState().updateIncident(incidentId, command),
  updateRisk: (riskId, command) => useDemo.getState().updateRisk(riskId, command),
  integrationCommand: (integrationId, command) => useDemo.getState().integrationCommand(integrationId, command),
  setAutonomy: (typeKey, actionKey, level) => useDemo.getState().setAutonomy(typeKey, actionKey, level),
  setNotification: (key, on) => useDemo.getState().setNotification(key, on),
};

export function useDataService(): DataService {
  return demoDataService;
}
