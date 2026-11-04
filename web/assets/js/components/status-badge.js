/* Status badge for workflow states. */

import { h, humanise } from "../core/format.js";

const TONE = {
  not_started: "neutral",
  ready: "info",
  in_progress: "accent",
  waiting_for_input: "warning",
  waiting_for_review: "warning",
  changes_requested: "warning",
  blocked: "danger",
  failed: "danger",
  completed: "success",
  cancelled: "muted",
  // approvals
  approved: "success",
  rejected: "danger",
  pending: "neutral",
  // decisions
  open: "info",
  deferred: "warning",
  decided: "success",
  // change requests
  applied: "success",
  // requirement items
  confirmed: "success",
  proposed: "warning",
  // agent runs
  queued: "info",
  running: "accent",
  succeeded: "success",
};

export function statusBadge(state) {
  return h("span", { class: `badge badge-${TONE[state] ?? "neutral"}` }, humanise(state));
}
