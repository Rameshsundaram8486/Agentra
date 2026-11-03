/* Page script: Decision detail - the original recommendation, options, and recording a human outcome. */

import { api } from "../../core/api.js";
import { control, formatDateTime, h } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";
import { statusBadge } from "../../components/status-badge.js";

const decisionId = param("id");
const ACTION_LABELS = {
  accept: "Accept the recommendation",
  modify: "Accept with changes",
  select_option: "Choose a different option",
  other: "Something else",
  reject: "Reject",
  defer: "Decide later",
};

function bullets(id, items) {
  document.getElementById(id).replaceChildren(...(items.length ? items.map((item) => h("li", {}, item)) : [h("li", { class: "muted" }, "None recorded")]));
}

function describeOutcome(decision, outcome) {
  const title = (key) => decision.options.find((o) => o.key === key)?.title ?? key;
  switch (outcome.action) {
    case "accept": return `Accepted: ${title(decision.recommended_option)}`;
    case "modify": return `Accepted with changes: ${title(decision.recommended_option)}`;
    case "select_option": return `Chose: ${title(outcome.selected_option)}`;
    case "other": return `Chose something else: ${outcome.custom_choice}`;
    case "reject": return "Rejected";
    default: return "Deferred";
  }
}

function render(decision) {
  const recommended = decision.options.find((o) => o.key === decision.recommended_option);
  document.title = `${decision.title} - Agentra`;
  document.getElementById("decision-title").textContent = decision.title;
  document.getElementById("raised").textContent = `Raised by ${decision.raised_by_name ?? "unknown"} on ${formatDateTime(decision.created_at)}`;
  document.getElementById("status").replaceChildren(statusBadge(decision.status));
  document.getElementById("question").textContent = decision.question;
  document.getElementById("context").textContent = decision.context ?? "";
  document.getElementById("recommendation-section").replaceChildren(
    recommended
      ? h(
          "div",
          { class: "recommendation" },
          h("div", { class: "small muted" }, "Recommendation (kept exactly as raised)"),
          h("strong", {}, recommended.title),
          h("p", {}, decision.recommendation_rationale),
        )
      : h("div", { class: "alert alert-info" }, "No recommendation was made; this is an open question."),
  );
  document.getElementById("options").replaceChildren(
    ...decision.options.map((option) =>
      h(
        "div",
        { class: `option ${option.key === decision.recommended_option ? "is-recommended" : ""}` },
        h("div", {}, h("strong", {}, option.title), option.key === decision.recommended_option ? h("span", { class: "tag" }, " recommended") : null),
        option.description ? h("div", { class: "small muted" }, option.description) : null,
      ),
    ),
  );
  bullets("assumptions", decision.assumptions);
  bullets("risks", decision.risks);
  document.getElementById("outcomes").replaceChildren(
    ...(decision.outcomes.length
      ? decision.outcomes.map((outcome) =>
          h(
            "li",
            {},
            h(
              "div",
              {},
              h("div", {}, h("strong", {}, describeOutcome(decision, outcome))),
              outcome.comment ? h("div", { class: "small" }, outcome.comment) : null,
              h("div", { class: "muted small" }, `${outcome.decided_by_name ?? "unknown"} - ${formatDateTime(outcome.created_at)}`),
            ),
          ),
        )
      : [h("li", { class: "muted" }, "Waiting for a decision.")]),
  );
  document.getElementById("decide").hidden = decision.status === "decided";
  if (decision.status !== "decided") renderDecideForm(decision);
}

function renderDecideForm(decision) {
  const form = document.getElementById("decide-form");
  const available = decision.recommended_option
    ? ["accept", "modify", "select_option", "other", "reject", "defer"]
    : ["select_option", "other", "reject", "defer"];
  document.getElementById("actions").replaceChildren(
    ...available.map((action, index) =>
      h("label", {}, h("input", { type: "radio", name: "outcome_action", value: action, checked: index === 0 }), ACTION_LABELS[action]),
    ),
  );
  const choices = decision.options.filter((o) => o.key !== decision.recommended_option);
  form.selected_option.replaceChildren(...choices.map((o) => h("option", { value: o.key }, o.title)));
  const sync = () => {
    const action = control(form, "outcome_action").value;
    document.getElementById("select-field").hidden = action !== "select_option";
    document.getElementById("other-field").hidden = action !== "other";
  };
  form.onchange = sync;
  sync();
}

async function load() {
  render(await api(`/api/decisions/${encodeURIComponent(decisionId)}`));
}

startPage(async () => {
  if (!decisionId) throw new Error("No decision selected");
  const decision = await api(`/api/decisions/${encodeURIComponent(decisionId)}`);
  document.getElementById("back-link").href = `decisions.html?id=${encodeURIComponent(decision.project_id)}`;
  render(decision);

  const form = document.getElementById("decide-form");
  const error = document.getElementById("decide-error");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    const action = control(form, "outcome_action").value;
    try {
      await api(`/api/decisions/${encodeURIComponent(decisionId)}/outcomes`, {
        method: "POST",
        body: {
          action,
          selected_option: action === "select_option" ? form.selected_option.value : null,
          custom_choice: action === "other" ? form.custom_choice.value.trim() : null,
          comment: form.comment.value.trim() || null,
        },
      });
      form.reset();
      await load();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
});
