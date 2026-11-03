/* Page script: Project workspace - phases with server-approved transitions, documents, decisions and team. */

import { api } from "../../core/api.js";
import { control, formatDateTime, h, humanise } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";
import { statusBadge } from "../../components/status-badge.js";

const projectId = param("id");
const ROLE_LABELS = {
  owner: "Owner",
  project_manager: "Project manager",
  reviewer: "Reviewer",
  customer_approver: "Customer approver",
  agent: "Agent",
};
let typeTitles = {};

const dialog = document.getElementById("transition-dialog");
const dialogForm = document.getElementById("transition-form");
const dialogError = document.getElementById("transition-error");
let pending = null;

function openTransition(phase, toState) {
  pending = { phase, toState };
  document.getElementById("transition-title").textContent = `Move Phase ${phase.phase} to "${humanise(toState)}"`;
  document.getElementById("transition-summary").textContent = `${phase.name}: currently ${humanise(phase.state)}.`;
  dialogForm.reason.value = "";
  dialogError.hidden = true;
  dialog.showModal();
  dialogForm.reason.focus();
}

document.getElementById("transition-cancel").addEventListener("click", () => dialog.close());

dialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const { phase, toState } = pending;
  try {
    await api(`/api/phase-runs/${encodeURIComponent(phase.id)}/transitions`, {
      method: "POST",
      body: { to_state: toState, reason: dialogForm.reason.value.trim(), expected_version: phase.version },
    });
    dialog.close();
    await loadPhases();
  } catch (failure) {
    dialogError.textContent = failure.message;
    dialogError.hidden = false;
    if (failure.code === "conflict") await loadPhases();
  }
});

function transitionButtons(phase) {
  if (phase.available_transitions.length === 0) return h("span", { class: "muted small" }, "-");
  return h(
    "div",
    { class: "actions" },
    phase.available_transitions.map((toState) =>
      h(
        "button",
        {
          class: `button button-small ${toState === "cancelled" || toState === "blocked" ? "button-danger" : "button-secondary"}`,
          type: "button",
          onclick: () => openTransition(phase, toState),
        },
        humanise(toState),
      ),
    ),
  );
}

async function loadPhases() {
  const phases = await api(`/api/projects/${encodeURIComponent(projectId)}/phases`);
  const rows = phases.map((phase) =>
    h(
      "tr",
      {},
      h("td", { class: "num" }, String(phase.phase)),
      h(
        "td",
        {},
        h("div", { class: "primary" }, phase.name),
        h("div", { class: "sub" }, `Agent: ${humanise(phase.primary_agent)}`),
        phase.required_approvals.length
          ? h("div", { class: "sub small" }, `Needs approved: ${phase.required_approvals.map((t) => typeTitles[t] ?? humanise(t)).join(", ")}`)
          : null,
      ),
      h("td", {}, statusBadge(phase.state), h("div", { class: "sub small" }, `v${phase.version} - ${formatDateTime(phase.updated_at)}`)),
      h("td", {}, transitionButtons(phase)),
    ),
  );
  document.getElementById("phases").replaceChildren(
    h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Phase"), h("th", {}, "State"), h("th", {}, "Actions"))), h("tbody", {}, rows)),
  );
}

async function loadDocuments() {
  const artifacts = await api(`/api/projects/${encodeURIComponent(projectId)}/artifacts`);
  const container = document.getElementById("documents");
  if (artifacts.length === 0) {
    container.replaceChildren(h("p", { class: "empty" }, "No documents yet."));
    return;
  }
  const rows = artifacts.map((artifact) =>
    h(
      "tr",
      {},
      h("td", {}, h("a", { class: "primary", href: `artifact.html?id=${encodeURIComponent(artifact.id)}` }, artifact.title), h("div", { class: "sub" }, artifact.type_title)),
      h("td", { class: "num" }, `v${artifact.current_version_no}`),
      h("td", {}, statusBadge(artifact.approval_status)),
      h("td", { class: "num" }, formatDateTime(artifact.updated_at)),
    ),
  );
  container.replaceChildren(
    h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "Document"), h("th", {}, "Version"), h("th", {}, "Approval"), h("th", {}, "Updated"))), h("tbody", {}, rows)),
  );
}

async function loadDecisionSummary() {
  const decisions = await api(`/api/projects/${encodeURIComponent(projectId)}/decisions`);
  const waiting = decisions.filter((d) => d.status !== "decided").length;
  document.getElementById("decision-summary").replaceChildren(
    h("p", {}, waiting === 0 ? "No decisions waiting." : `${waiting} decision${waiting === 1 ? "" : "s"} waiting for a person.`),
    h("p", { class: "muted small" }, `${decisions.length} in total.`),
  );
}

function enableNewDocument(types) {
  const toggle = document.getElementById("new-document-toggle");
  const section = document.getElementById("new-document");
  const form = document.getElementById("new-document-form");
  const error = document.getElementById("new-document-error");
  form.artifact_type.replaceChildren(...types.map((type) => h("option", { value: type.key }, type.title)));
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    section.hidden = false;
    toggle.hidden = true;
    control(form, "title").focus();
  });
  document.getElementById("new-document-cancel").addEventListener("click", () => {
    section.hidden = true;
    toggle.hidden = false;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      const artifact = await api(`/api/projects/${encodeURIComponent(projectId)}/artifacts`, {
        method: "POST",
        body: {
          artifact_type: form.artifact_type.value,
          title: control(form, "title").value.trim(),
          content: form.content.value,
          source_refs: form.sources.value.split(",").map((s) => s.trim()).filter(Boolean),
        },
      });
      location.assign(`artifact.html?id=${encodeURIComponent(artifact.id)}`);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
}

async function loadMembers() {
  const members = await api(`/api/projects/${encodeURIComponent(projectId)}/members`);
  document.getElementById("members").replaceChildren(
    ...members.map((member) =>
      h(
        "li",
        {},
        h("div", {}, h("div", {}, member.display_name), h("div", { class: "muted small" }, member.email)),
        h("span", { class: "tag" }, ROLE_LABELS[member.role] ?? member.role),
      ),
    ),
  );
}

function enableAddMember() {
  const form = document.getElementById("add-member-form");
  const error = document.getElementById("member-error");
  form.hidden = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      await api(`/api/projects/${encodeURIComponent(projectId)}/members`, {
        method: "POST",
        body: { email: form.email.value.trim(), role: form.role.value },
      });
      form.reset();
      await loadMembers();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
}

startPage(async () => {
  if (!projectId) throw new Error("No project selected");
  const [detail, types] = await Promise.all([api(`/api/projects/${encodeURIComponent(projectId)}`), api("/api/artifact-types")]);
  typeTitles = Object.fromEntries(types.map((type) => [type.key, type.title]));
  const project = detail.project;
  const can = (permission) => detail.my_permissions.includes(permission);
  document.title = `${project.name} - Agentra`;
  document.getElementById("project-name").textContent = project.name;
  const roles = detail.my_roles.length ? detail.my_roles.map((role) => ROLE_LABELS[role] ?? role).join(", ") : "not a member";
  document.getElementById("project-meta").textContent = `${project.code} - ${project.customer_name} - Your role: ${roles}`;
  document.getElementById("decisions-link").href = `decisions.html?id=${encodeURIComponent(project.id)}`;
  if (can("audit.view")) {
    const link = document.getElementById("audit-link");
    link.href = `audit.html?id=${encodeURIComponent(project.id)}`;
    link.hidden = false;
  }
  if (can("project.manage_members")) enableAddMember();
  if (can("artifact.author")) enableNewDocument(types);
  await Promise.all([
    loadPhases(),
    loadMembers(),
    can("artifact.view") ? loadDocuments() : Promise.resolve(),
    can("decision.view") ? loadDecisionSummary() : Promise.resolve(),
  ]);
});
