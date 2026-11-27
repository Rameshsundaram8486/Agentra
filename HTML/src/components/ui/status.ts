/* The one status vocabulary of the demo: every state shown anywhere has a label, a tone and an icon, so status never
   relies on colour alone and means the same on every screen. */
import {
  Ban, CircleCheck, CircleDot, CirclePause, CircleX, Clock, Hourglass, LoaderCircle, MessageCircleQuestion, RotateCcw, ShieldExclamationPoint,
  TriangleExclamationPoint, UserCheck, type LucideIcon,
} from "lucide-react";
import type { AgentStatus, ArtifactStatus, DecisionStatus, ExecutionStatus, Health, IncidentStatus, PhaseState, Priority, RiskStatus, TaskState } from "@/types";

export type Tone = "primary" | "cyan" | "violet" | "success" | "warning" | "danger" | "neutral";

export interface StatusMeta {
  label: string;
  tone: Tone;
  icon: LucideIcon;
}

export const TONE_TEXT: Record<Tone, string> = {
  primary: "text-primary-strong",
  cyan: "text-cyan",
  violet: "text-violet",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  neutral: "text-fg-muted",
};

export const TONE_SOFT: Record<Tone, string> = {
  primary: "bg-primary-soft text-primary-strong",
  cyan: "bg-cyan-soft text-cyan",
  violet: "bg-violet-soft text-violet",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  neutral: "bg-neutral-soft text-fg-muted",
};

export const TONE_DOT: Record<Tone, string> = {
  primary: "bg-primary",
  cyan: "bg-cyan",
  violet: "bg-violet",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-neutral",
};

/** Chart colours as CSS variables, so charts follow the theme. */
export const TONE_VAR: Record<Tone, string> = {
  primary: "var(--primary)",
  cyan: "var(--cyan)",
  violet: "var(--violet)",
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  neutral: "var(--neutral)",
};

export const AGENT_STATUS: Record<AgentStatus, StatusMeta> = {
  working: { label: "Working", tone: "primary", icon: LoaderCircle },
  idle: { label: "Idle", tone: "neutral", icon: CircleDot },
  waiting_approval: { label: "Waiting for a person", tone: "violet", icon: UserCheck },
  blocked: { label: "Blocked", tone: "warning", icon: Ban },
  failed: { label: "Failed", tone: "danger", icon: CircleX },
  completed: { label: "Completed", tone: "success", icon: CircleCheck },
};

export const TASK_STATE: Record<TaskState, StatusMeta> = {
  not_started: { label: "Not started", tone: "neutral", icon: CircleDot },
  ready: { label: "Ready", tone: "cyan", icon: CircleDot },
  in_progress: { label: "In progress", tone: "primary", icon: LoaderCircle },
  waiting_for_input: { label: "Waiting for input", tone: "violet", icon: MessageCircleQuestion },
  waiting_for_review: { label: "Waiting for review", tone: "violet", icon: UserCheck },
  changes_requested: { label: "Changes requested", tone: "warning", icon: RotateCcw },
  blocked: { label: "Blocked", tone: "warning", icon: Ban },
  failed: { label: "Failed", tone: "danger", icon: CircleX },
  completed: { label: "Completed", tone: "success", icon: CircleCheck },
  cancelled: { label: "Cancelled", tone: "neutral", icon: CircleX },
};

export const HEALTH: Record<Health, StatusMeta> = {
  on_track: { label: "On track", tone: "success", icon: CircleCheck },
  at_risk: { label: "At risk", tone: "warning", icon: TriangleExclamationPoint },
  critical: { label: "Critical", tone: "danger", icon: ShieldExclamationPoint },
  on_hold: { label: "On hold", tone: "neutral", icon: CirclePause },
  completed: { label: "Completed", tone: "cyan", icon: CircleCheck },
};

export const PHASE_STATE: Record<PhaseState, StatusMeta> = {
  completed: { label: "Completed", tone: "success", icon: CircleCheck },
  active: { label: "Active", tone: "primary", icon: LoaderCircle },
  awaiting_approval: { label: "Awaiting approval", tone: "violet", icon: UserCheck },
  blocked: { label: "Blocked", tone: "warning", icon: Ban },
  upcoming: { label: "Upcoming", tone: "neutral", icon: CircleDot },
};

export const DECISION_STATUS: Record<DecisionStatus, StatusMeta> = {
  pending: { label: "Pending", tone: "violet", icon: Hourglass },
  approved: { label: "Approved", tone: "success", icon: CircleCheck },
  modified: { label: "Modified", tone: "cyan", icon: CircleCheck },
  rejected: { label: "Rejected", tone: "danger", icon: CircleX },
  deferred: { label: "Deferred", tone: "neutral", icon: Clock },
  clarification_requested: { label: "Clarification requested", tone: "warning", icon: MessageCircleQuestion },
};

export const EXECUTION_STATUS: Record<ExecutionStatus, StatusMeta> = {
  queued: { label: "Queued", tone: "neutral", icon: Clock },
  running: { label: "Running", tone: "primary", icon: LoaderCircle },
  paused: { label: "Paused", tone: "warning", icon: CirclePause },
  retrying: { label: "Retrying", tone: "cyan", icon: RotateCcw },
  succeeded: { label: "Succeeded", tone: "success", icon: CircleCheck },
  failed: { label: "Failed", tone: "danger", icon: CircleX },
};

export const PRIORITY: Record<Priority, StatusMeta> = {
  critical: { label: "Critical", tone: "danger", icon: ShieldExclamationPoint },
  high: { label: "High", tone: "warning", icon: TriangleExclamationPoint },
  medium: { label: "Medium", tone: "primary", icon: CircleDot },
  low: { label: "Low", tone: "neutral", icon: CircleDot },
};

export const INCIDENT_STATUS: Record<IncidentStatus, StatusMeta> = {
  open: { label: "Open", tone: "danger", icon: TriangleExclamationPoint },
  investigating: { label: "Investigating", tone: "warning", icon: LoaderCircle },
  resolved: { label: "Resolved", tone: "cyan", icon: CircleCheck },
  closed: { label: "Closed", tone: "success", icon: CircleCheck },
};

export const RISK_STATUS: Record<RiskStatus, StatusMeta> = {
  open: { label: "Open", tone: "danger", icon: TriangleExclamationPoint },
  mitigating: { label: "Mitigating", tone: "warning", icon: LoaderCircle },
  closed: { label: "Closed", tone: "success", icon: CircleCheck },
};

export const ARTIFACT_STATUS: Record<ArtifactStatus, StatusMeta> = {
  draft: { label: "Draft", tone: "neutral", icon: CircleDot },
  in_review: { label: "In review", tone: "violet", icon: UserCheck },
  changes_requested: { label: "Changes requested", tone: "warning", icon: RotateCcw },
  approved: { label: "Approved", tone: "success", icon: CircleCheck },
};
