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
};

export function statusBadge(state) {
  return h("span", { class: `badge badge-${TONE[state] ?? "neutral"}` }, humanise(state));
}
