/* Page script: Decision inbox for a project, and raising a new decision request. */

import { api } from "../../core/api.js";
import { control, formatDateTime, h } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";
import { statusBadge } from "../../components/status-badge.js";

const projectId = param("id");

function lines(text) {
  return text.split("\n").map((line) => line.trim()).filter(Boolean);
}

function parseOptions(text) {
  return lines(text).map((line, index) => {
    const [title, ...rest] = line.split(" - ");
    return { key: `opt-${index + 1}`, title: title.trim().slice(0, 200), description: rest.join(" - ").trim() };
  });
}

function renderList(decisions) {
  const container = document.getElementById("decision-list");
  if (decisions.length === 0) {
    container.replaceChildren(h("p", { class: "empty" }, "No decisions yet."));
    return;
  }
  const order = { open: 0, deferred: 1, decided: 2 };
  const sorted = [...decisions].sort((a, b) => order[a.status] - order[b.status]);
  container.replaceChildren(
    h(
      "table",
      { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "Decision"), h("th", {}, "Status"), h("th", {}, "Outcome"), h("th", {}, "Raised"))),
      h(
        "tbody",
        {},
        sorted.map((decision) =>
          h(
            "tr",
            {},
            h("td", {}, h("a", { class: "primary", href: `decision.html?id=${encodeURIComponent(decision.id)}` }, decision.title), h("div", { class: "sub" }, decision.question)),
            h("td", {}, statusBadge(decision.status)),
            h("td", {}, decision.final_choice ?? (decision.status === "decided" ? "Rejected" : "-")),
            h("td", { class: "num" }, h("div", {}, decision.raised_by_name ?? ""), h("div", { class: "sub" }, formatDateTime(decision.created_at))),
          ),
        ),
      ),
    ),
  );
}

function enableRaise() {
  const toggle = document.getElementById("raise-toggle");
  const section = document.getElementById("raise");
  const form = document.getElementById("raise-form");
  const error = document.getElementById("raise-error");
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    section.hidden = false;
    toggle.hidden = true;
  });
  document.getElementById("raise-cancel").addEventListener("click", () => {
    section.hidden = true;
    toggle.hidden = false;
  });
  form.options.addEventListener("input", () => {
    const previous = form.recommended.value;
    form.recommended.replaceChildren(
      h("option", { value: "" }, "No recommendation"),
      ...parseOptions(form.options.value).map((option) => h("option", { value: option.key }, option.title)),
    );
    form.recommended.value = [...form.recommended.options].some((o) => o.value === previous) ? previous : "";
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      const decision = await api(`/api/projects/${encodeURIComponent(projectId)}/decisions`, {
        method: "POST",
        body: {
          title: control(form, "title").value.trim(),
          question: form.question.value.trim(),
          context: form.context.value.trim() || null,
          options: parseOptions(form.options.value),
          recommended_option: form.recommended.value || null,
          recommendation_rationale: form.rationale.value.trim(),
          assumptions: lines(form.assumptions.value),
          risks: lines(form.risks.value),
        },
      });
      location.assign(`decision.html?id=${encodeURIComponent(decision.id)}`);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
}

startPage(async () => {
  if (!projectId) throw new Error("No project selected");
  const [detail, decisions] = await Promise.all([
    api(`/api/projects/${encodeURIComponent(projectId)}`),
    api(`/api/projects/${encodeURIComponent(projectId)}/decisions`),
  ]);
  const link = document.getElementById("project-link");
  link.textContent = detail.project.name;
  link.href = `project.html?id=${encodeURIComponent(projectId)}`;
  if (detail.my_permissions.includes("decision.raise")) enableRaise();
  renderList(decisions);
});
