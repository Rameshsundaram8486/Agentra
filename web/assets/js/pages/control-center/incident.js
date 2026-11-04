/* Page script: Incident detail - facts captured when it opened, its history, and the resolve and close forms. */

import { api } from "../../core/api.js";
import { control, formatDateTime, h, humanise } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";
import { statusBadge } from "../../components/status-badge.js";

const incidentId = param("id");
const FACTS = [
  ["error_code", "Error"],
  ["error_message", "Message"],
  ["task", "Agent task"],
  ["input", "Input"],
  ["attempts", "Attempts"],
  ["workflow_task_state", "Task state when it failed"],
  ["prompt_version", "Prompt version"],
  ["recorded_at", "Recorded"],
];

function kv(pairs) {
  return pairs.filter(([, value]) => value !== null && value !== undefined && value !== "").flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, String(value))]);
}

function describe(event) {
  if (event.event === "recurrence") return `Happened again (run ${event.data.run_id})`;
  if (event.event === "resolved") return `Resolved by ${event.actor_name ?? "someone"}: ${event.data.cause} (${event.data.cause_certainty})`;
  return `Verified and closed by ${event.actor_name ?? "someone"}: ${event.data.verification_evidence}`;
}

function render(incident) {
  document.title = `${incident.incident_id} - Agentra`;
  document.getElementById("incident-title").textContent = `${incident.incident_id}: ${incident.title}`;
  document.getElementById("back-link").href = `project.html?id=${encodeURIComponent(incident.project_id)}`;
  document.getElementById("incident-meta").textContent = `${humanise(incident.category)}, severity ${incident.severity}, opened ${formatDateTime(incident.opened_at)}, occurred ${incident.occurrences} time(s)`;
  document.getElementById("status").replaceChildren(statusBadge(incident.status));
  const evidence = incident.evidence;
  document.getElementById("facts").replaceChildren(
    ...kv(FACTS.map(([key, label]) => [label, evidence[key]])),
    ...kv([["Blocking findings", (evidence.blocking_findings ?? []).map((f) => `${f.check}: ${f.message}`).join("; ")]]),
    ...kv([["Model calls", (evidence.model_calls ?? []).map((c) => `${c.status} ${c.model ?? ""} ${c.stop_reason ?? ""} $${c.cost_usd}`).join("; ")]]),
  );
  document.getElementById("events").replaceChildren(
    ...(incident.events.length
      ? incident.events.map((event) => h("li", {}, h("div", {}, describe(event)), h("span", { class: "muted small" }, formatDateTime(event.created_at))))
      : [h("li", { class: "muted" }, "No events since it opened.")]),
  );
  const rca = incident.rca;
  document.getElementById("rca").replaceChildren(
    rca
      ? h(
          "dl",
          { class: "kv" },
          ...kv([
            [`Cause (${rca.cause_certainty})`, rca.cause],
            ["Contributing factors", rca.contributing_factors],
            ["Containment", rca.containment],
            ["Corrective action", rca.corrective_action],
            ["Owner", rca.action_owner_name],
            ["Target date", rca.target_date],
            ["Verification criteria", rca.verification_criteria],
            ["Resolved by", `${rca.resolved_by_name ?? "someone"}, ${formatDateTime(rca.resolved_at)}`],
            ["Verification", incident.verification_evidence ? `${incident.verification_evidence} (${incident.closed_by_name})` : null],
          ]),
        )
      : h("p", { class: "muted" }, "No root-cause analysis yet."),
  );
}

async function submit(form, errorId, path, body) {
  const error = document.getElementById(errorId);
  error.hidden = true;
  try {
    const incident = await api(`/api/incidents/${encodeURIComponent(incidentId)}/${path}`, { method: "POST", body });
    render(incident);
    show(incident);
    form.reset();
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
  }
}

function show(incident) {
  document.getElementById("resolve").hidden = incident.status !== "open";
  document.getElementById("close").hidden = incident.status !== "resolved";
}

startPage(async () => {
  if (!incidentId) throw new Error("No incident selected");
  const incident = await api(`/api/incidents/${encodeURIComponent(incidentId)}`);
  render(incident);
  show(incident);
  const resolveForm = document.getElementById("resolve-form");
  resolveForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = (name) => control(resolveForm, name).value.trim();
    submit(resolveForm, "resolve-error", "resolution", {
      cause: value("cause"),
      cause_certainty: value("cause_certainty"),
      contributing_factors: value("contributing_factors"),
      containment: value("containment"),
      corrective_action: value("corrective_action"),
      action_owner_email: value("action_owner_email"),
      target_date: value("target_date"),
      verification_criteria: value("verification_criteria"),
    });
  });
  const closeForm = document.getElementById("close-form");
  closeForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submit(closeForm, "close-error", "closure", { verification_evidence: control(closeForm, "verification_evidence").value.trim() });
  });
});
