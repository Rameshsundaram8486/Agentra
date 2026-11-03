/* Page script: Artifact viewer - versions, content, diff, version-bound review and new versions. */

import { api } from "../../core/api.js";
import { formatDateTime, h, humanise } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";
import { statusBadge } from "../../components/status-badge.js";

const artifactId = param("id");
let page = null; // { artifact, approvals, people }
let shown = null; // { version, content } currently displayed

function person(id) {
  return page.people[id] ?? "unknown";
}

async function showVersion(version) {
  const result = await api(`/api/artifact-versions/${encodeURIComponent(version.id)}/content`);
  shown = result;
  const current = version.version_no === page.artifact.current_version_no;
  document.getElementById("viewing-label").textContent = `Version ${version.version_no}`;
  document.getElementById("viewing-note").textContent = current ? "Current version" : "Older version - read only";
  document.getElementById("version-meta").replaceChildren(
    h("dt", {}, "Author"), h("dd", {}, person(version.author_id)),
    h("dt", {}, "Created"), h("dd", {}, formatDateTime(version.created_at)),
    h("dt", {}, "Change"), h("dd", {}, version.change_summary),
    h("dt", {}, "Sources"), h("dd", {}, version.source_refs.length ? version.source_refs.join("; ") : "none recorded"),
    h("dt", {}, "SHA-256"), h("dd", { class: "hash" }, result.version.content_sha256),
  );
  document.getElementById("content").textContent = result.content;
  document.getElementById("review-panel").hidden = !current;
  for (const button of document.querySelectorAll("#versions button")) {
    button.setAttribute("aria-current", String(button.dataset.version === String(version.version_no)));
  }
}

function renderVersions() {
  const versions = page.artifact.versions;
  document.getElementById("versions").replaceChildren(
    ...versions.map((version) =>
      h(
        "li",
        {},
        h(
          "button",
          { type: "button", "data-version": String(version.version_no), onclick: () => showVersion(version) },
          h("div", {}, h("strong", {}, `v${version.version_no}`), " ", version.change_summary),
          h("div", { class: "muted small" }, `${person(version.author_id)} - ${formatDateTime(version.created_at)}`),
        ),
      ),
    ),
  );
  for (const id of ["compare-from", "compare-to"]) {
    document.getElementById(id).replaceChildren(...versions.map((v) => h("option", { value: String(v.version_no) }, `v${v.version_no}`)));
  }
  document.getElementById("compare-panel").hidden = versions.length < 2;
  if (versions.length >= 2) {
    document.getElementById("compare-from").value = String(versions[1].version_no);
    document.getElementById("compare-to").value = String(versions[0].version_no);
  }
}

function renderApprovals() {
  const { current, history } = page.approvals;
  document.getElementById("approval-status").replaceChildren(h("span", { class: "muted small" }, `v${current.version_no}: `), statusBadge(current.status));
  const list = document.getElementById("history");
  if (history.length === 0) {
    list.replaceChildren(h("li", { class: "muted" }, "No reviews yet."));
    return;
  }
  list.replaceChildren(
    ...history.map((approval) =>
      h(
        "li",
        {},
        h(
          "div",
          {},
          h("div", {}, statusBadge(approval.decision), " ", h("strong", {}, `v${approval.version_no}`), ` by ${approval.approver_name ?? "unknown"}`),
          approval.comment ? h("div", { class: "small" }, approval.comment) : null,
          h("div", { class: "hash" }, `${formatDateTime(approval.created_at)} - sha256 ${approval.content_sha256.slice(0, 16)}...`),
        ),
      ),
    ),
  );
}

async function reload() {
  page = await api(`/api/artifacts/${encodeURIComponent(artifactId)}`);
  const { artifact } = page;
  document.title = `${artifact.title} - Agentra`;
  document.getElementById("artifact-title").textContent = artifact.title;
  document.getElementById("artifact-type").textContent = `${artifact.type_title} - version ${artifact.current_version_no}`;
  renderVersions();
  renderApprovals();
  await showVersion(artifact.current_version);
}

function wireReview() {
  const message = document.getElementById("review-message");
  const comment = document.getElementById("review-comment");
  for (const button of document.querySelectorAll("#review-panel [data-decision]")) {
    button.addEventListener("click", async () => {
      message.hidden = true;
      try {
        await api(`/api/artifact-versions/${encodeURIComponent(shown.version.id)}/approvals`, {
          method: "POST",
          body: { decision: button.dataset.decision, content_sha256: shown.version.content_sha256, comment: comment.value.trim() || null },
        });
        comment.value = "";
        await reload();
        message.className = "alert alert-success";
        message.textContent = `Recorded: ${humanise(button.dataset.decision)} for version ${shown.version.version_no}.`;
      } catch (failure) {
        message.className = "alert alert-error";
        message.textContent = failure.message;
      }
      message.hidden = false;
    });
  }
}

function wireCompare() {
  document.getElementById("compare").addEventListener("click", async () => {
    const from = document.getElementById("compare-from").value;
    const to = document.getElementById("compare-to").value;
    const result = await api(`/api/artifacts/${encodeURIComponent(artifactId)}/diff?from_version=${from}&to_version=${to}`);
    const lines = result.diff ? result.diff.split("\n") : ["No differences."];
    document.getElementById("diff").replaceChildren(
      ...lines.map((line) => {
        let tone = "";
        if (line.startsWith("+") && !line.startsWith("+++")) tone = "diff-add";
        else if (line.startsWith("-") && !line.startsWith("---")) tone = "diff-del";
        else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) tone = "diff-meta";
        return h("span", { class: `diff-line ${tone}` }, line || " ");
      }),
    );
    document.getElementById("diff").hidden = false;
  });
}

function enableNewVersion() {
  const section = document.getElementById("new-version");
  const form = document.getElementById("new-version-form");
  const error = document.getElementById("new-version-error");
  section.hidden = false;
  const prefill = () => {
    form.content.value = shown.content;
    form.sources.value = shown.version.source_refs.join(", ");
  };
  prefill();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      await api(`/api/artifacts/${encodeURIComponent(artifactId)}/versions`, {
        method: "POST",
        body: {
          content: form.content.value,
          change_summary: form.change_summary.value.trim(),
          source_refs: form.sources.value.split(",").map((s) => s.trim()).filter(Boolean),
          expected_current_version: page.artifact.current_version_no,
        },
      });
      form.change_summary.value = "";
      await reload();
      prefill();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
}

startPage(async () => {
  if (!artifactId) throw new Error("No document selected");
  await reload();
  const detail = await api(`/api/projects/${encodeURIComponent(page.artifact.project_id)}`);
  const link = document.getElementById("project-link");
  link.textContent = detail.project.name;
  link.href = `project.html?id=${encodeURIComponent(detail.project.id)}`;
  wireReview();
  wireCompare();
  if (detail.my_permissions.includes("artifact.author")) enableNewVersion();
});
