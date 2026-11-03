/* Page script: Project workspace - phases and tasks with server-approved transitions, documents and uploads,
   requirements, agent runs, decisions and team. */

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

function openTransition(kind, entity, toState) {
  pending = { kind, entity, toState };
  const label = kind === "phase" ? `Phase ${entity.phase}` : `the "${entity.title}" task`;
  document.getElementById("transition-title").textContent = `Move ${label} to "${humanise(toState)}"`;
  document.getElementById("transition-summary").textContent = `${kind === "phase" ? entity.name : entity.title}: currently ${humanise(entity.state)}.`;
  dialogForm.reason.value = "";
  dialogError.hidden = true;
  dialog.showModal();
  dialogForm.reason.focus();
}

document.getElementById("transition-cancel").addEventListener("click", () => dialog.close());

dialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const { kind, entity, toState } = pending;
  const path = kind === "phase" ? "phase-runs" : "tasks";
  try {
    await api(`/api/${path}/${encodeURIComponent(entity.id)}/transitions`, {
      method: "POST",
      body: { to_state: toState, reason: dialogForm.reason.value.trim(), expected_version: entity.version },
    });
    dialog.close();
    await loadPhases();
  } catch (failure) {
    dialogError.textContent = failure.message;
    dialogError.hidden = false;
    if (failure.code === "conflict") await loadPhases();
  }
});

function transitionButtons(kind, entity) {
  if (entity.available_transitions.length === 0) return h("span", { class: "muted small" }, "-");
  return h(
    "div",
    { class: "actions" },
    entity.available_transitions.map((toState) =>
      h(
        "button",
        {
          class: `button button-small ${toState === "cancelled" || toState === "blocked" ? "button-danger" : "button-secondary"}`,
          type: "button",
          onclick: () => openTransition(kind, entity, toState),
        },
        humanise(toState),
      ),
    ),
  );
}

async function loadPhases() {
  const phases = await api(`/api/projects/${encodeURIComponent(projectId)}/phases`);
  const rows = phases.flatMap((phase) => [
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
      h("td", {}, transitionButtons("phase", phase)),
    ),
    ...phase.tasks.map((task) =>
      h(
        "tr",
        { "data-task": task.key },
        h("td", { class: "num muted small" }, "task"),
        h(
          "td",
          {},
          h("div", {}, task.title),
          h("div", { class: "sub" }, task.agent ? `Agent: ${humanise(task.agent)}` : "People"),
          task.depends_on.length ? h("div", { class: "sub small" }, `After: ${task.depends_on.map(humanise).join(", ")}`) : null,
        ),
        h("td", {}, statusBadge(task.state)),
        h("td", {}, transitionButtons("task", task)),
      ),
    ),
  ]);
  document.getElementById("phases").replaceChildren(
    h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Phase"), h("th", {}, "State"), h("th", {}, "Actions"))), h("tbody", {}, rows)),
  );
}

async function loadDocuments() {
  const artifacts = await api(`/api/projects/${encodeURIComponent(projectId)}/artifacts`);
  const container = document.getElementById("documents");
  if (artifacts.length === 0) {
    container.replaceChildren(h("p", { class: "empty" }, "No documents yet."));
    return artifacts;
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
  return artifacts;
}

// Agent runs ----------------------------------------------------------------------------------

const RUN_POLL_MS = 4000;
let runPoll = null;
let runsBusy = false;

function money(value) {
  return `$${Number(value).toFixed(2)}`;
}

function runItem(run) {
  const meta = [run.model, Number(run.cost_usd) > 0 ? money(run.cost_usd) : null, run.attempts > 1 ? `attempt ${run.attempts} of ${run.max_attempts}` : null].filter(Boolean);
  const blocking = run.findings.filter((finding) => finding.severity === "block");
  const warnings = run.findings.filter((finding) => finding.severity === "warn");
  return h(
    "li",
    {},
    h(
      "div",
      {},
      h("div", {}, `${run.task_title}: ${run.input_title} v${run.input_version_no}`),
      run.context_documents || run.context_decisions
        ? h("div", { class: "muted small" }, `Also read ${run.context_documents} other document(s) and ${run.context_decisions} decision(s)`)
        : null,
      h("div", { class: "muted small" }, `Asked by ${run.requested_by_name ?? "unknown"} - ${formatDateTime(run.created_at)}`),
      meta.length ? h("div", { class: "muted small" }, meta.join(" - ")) : null,
      run.status === "queued" ? h("div", { class: "muted small" }, "Waiting for the agent worker (scripts\\run_workers.ps1).") : null,
      run.status === "succeeded" && run.decision_ids.length
        ? h("div", { class: "small" }, h("a", { href: `decisions.html?id=${encodeURIComponent(projectId)}` }, `${run.decision_ids.length} question(s) are in the decision inbox`))
        : null,
      run.status === "succeeded" && run.task_key === "draft_requirements" ? h("div", { class: "small" }, "The draft is in Requirements below.") : null,
      run.error_message ? h("div", { class: "small" }, run.error_message) : null,
      blocking.length ? h("ul", { class: "bullets small" }, blocking.map((finding) => h("li", {}, finding.path ? `${finding.path}: ${finding.message}` : finding.message))) : null,
      warnings.length ? h("div", { class: "muted small" }, `Noted: ${warnings.map((finding) => finding.message).join("; ")}`) : null,
    ),
    statusBadge(run.status),
  );
}

async function loadAgentRuns() {
  const runs = await api(`/api/projects/${encodeURIComponent(projectId)}/agent-runs`);
  document.getElementById("agent-runs").replaceChildren(...runs.map(runItem));
  const busy = runs.some((run) => run.status === "queued" || run.status === "running");
  if (runsBusy && !busy) refreshAfterRun().catch(() => {});
  runsBusy = busy;
  clearTimeout(runPoll);
  if (busy) runPoll = setTimeout(() => loadAgentRuns().catch(() => {}), RUN_POLL_MS);
}

// Requirements -------------------------------------------------------------------------------

function flagLines(flags) {
  return flags.map((flag) => h("div", { class: flag.severity === "warning" ? "small" : "muted small" }, `${flag.severity === "warning" ? "Warning" : "Note"}: ${flag.message}`));
}

async function loadRequirements() {
  const section = document.getElementById("requirements-section");
  const view = await api(`/api/projects/${encodeURIComponent(projectId)}/requirements`);
  section.hidden = false;
  document.getElementById("requirements").hidden = !view;
  if (!view) {
    document.getElementById("requirements-summary").replaceChildren(
      h("p", { class: "muted" }, "Not drafted yet. Ask the Business Analyst agent to draft the requirements once the brief has been clarified."),
    );
    document.getElementById("requirements").replaceChildren();
    return;
  }
  const changes = view.version_no > 1 ? ` Added: ${view.added.join(", ") || "none"}. Removed: ${view.removed.join(", ") || "none"}.` : "";
  document.getElementById("requirements-summary").replaceChildren(
    h(
      "div",
      { class: "section-header" },
      h("a", { class: "primary", href: `artifact.html?id=${encodeURIComponent(view.artifact_id)}` }, `${view.artifact_title} v${view.version_no}`),
      statusBadge(view.approval_status),
    ),
    h("p", {}, view.summary),
    h("p", { class: "muted small" }, `${view.counts.confirmed} confirmed, ${view.counts.proposed} proposed, ${view.counts.open} open.${changes} Review and approve it on the document page.`),
    ...flagLines(view.set_flags),
  );
  const rows = view.items.map((item) =>
    h(
      "tr",
      {},
      h("td", { class: "num" }, item.item_id),
      h(
        "td",
        {},
        h("div", { class: "primary" }, item.title),
        h("div", { class: "sub" }, item.statement),
        item.acceptance_criteria.length ? h("ul", { class: "bullets small" }, item.acceptance_criteria.map((c) => h("li", {}, c))) : null,
        ...flagLines(item.quality_flags),
      ),
      h("td", { class: "small" }, humanise(item.kind), h("div", { class: "sub" }, humanise(item.label))),
      h("td", {}, statusBadge(item.status)),
    ),
  );
  document.getElementById("requirements").replaceChildren(
    h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "ID"), h("th", {}, "Requirement"), h("th", {}, "Kind"), h("th", {}, "Status"))), h("tbody", {}, rows)),
  );
}

async function refreshAfterRun() {
  await Promise.all([
    loadPhases(),
    loadDecisionSummary(),
    loadRequirements(),
    loadDocuments().then((artifacts) => fillBriefs(artifacts)),
  ]);
}

// Uploads ------------------------------------------------------------------------------------

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(new Error("The file could not be read"));
    reader.readAsDataURL(file);
  });
}

function enableUpload() {
  const toggle = document.getElementById("upload-toggle");
  const section = document.getElementById("upload");
  const form = document.getElementById("upload-form");
  const error = document.getElementById("upload-error");
  const submit = document.getElementById("upload-submit");
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    section.hidden = false;
    toggle.hidden = true;
  });
  document.getElementById("upload-cancel").addEventListener("click", () => {
    section.hidden = true;
    toggle.hidden = false;
  });
  control(form, "file").addEventListener("change", () => {
    const title = control(form, "title");
    if (!title.value && control(form, "file").files[0]) title.value = control(form, "file").files[0].name.replace(/\.[^.]+$/, "");
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    const file = control(form, "file").files[0];
    if (!file) return;
    submit.disabled = true;
    try {
      const artifact = await api(`/api/projects/${encodeURIComponent(projectId)}/artifacts/upload`, {
        method: "POST",
        body: {
          artifact_type: form.artifact_type.value,
          title: control(form, "title").value.trim(),
          filename: file.name,
          origin: control(form, "origin").value.trim(),
          content_base64: await readAsBase64(file),
        },
      });
      location.assign(`artifact.html?id=${encodeURIComponent(artifact.id)}`);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

// Agent ----------------------------------------------------------------------------------------

function fillBriefs(artifacts) {
  const briefs = artifacts.filter((artifact) => artifact.artifact_type === "project_brief");
  const form = document.getElementById("agent-form");
  form.artifact_version_id.replaceChildren(
    ...briefs.map((brief) => h("option", { value: brief.current_version.id }, `${brief.title} (v${brief.current_version_no})`)),
  );
  return briefs;
}

function enableAgent(artifacts, canRun) {
  document.getElementById("agent-section").hidden = false;
  if (!canRun) return;
  const briefs = fillBriefs(artifacts);
  if (briefs.length === 0) {
    document.getElementById("agent-no-brief").hidden = false;
    return;
  }
  const form = document.getElementById("agent-form");
  const message = document.getElementById("agent-error");
  const submit = document.getElementById("agent-submit");
  form.hidden = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.hidden = true;
    submit.disabled = true;
    try {
      const result = await api(`/api/projects/${encodeURIComponent(projectId)}/agent-runs`, {
        method: "POST",
        body: { agent_key: "business_analyst", task_key: control(form, "task_key").value, artifact_version_id: form.artifact_version_id.value },
      });
      if (!result.created) {
        message.className = "alert alert-info";
        message.textContent = "The agent has already done this task with exactly these inputs; see its run below.";
        message.hidden = false;
      }
      await Promise.all([loadAgentRuns(), loadPhases()]);
    } catch (failure) {
      message.className = "alert alert-error";
      message.textContent = failure.message;
      message.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
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
  if (can("artifact.author")) {
    enableNewDocument(types);
    enableUpload();
  }
  const [, , artifacts] = await Promise.all([
    loadPhases(),
    loadMembers(),
    can("artifact.view") ? loadDocuments() : Promise.resolve([]),
    can("decision.view") ? loadDecisionSummary() : Promise.resolve(),
  ]);
  if (can("artifact.view")) await loadRequirements();
  if (can("agent_run.view")) {
    enableAgent(artifacts, can("agent.run"));
    await loadAgentRuns();
  }
});
