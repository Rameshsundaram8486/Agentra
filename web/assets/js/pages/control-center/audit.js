/* Page script: Project audit trail with paging, and hash-chain verification for platform admins. */

import { api } from "../../core/api.js";
import { formatDateTime, h, humanise } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";

const projectId = param("id");
const PAGE_SIZE = 50;
let tbody = null;
let oldestSeq = null;

function change(event) {
  const before = event.before?.state;
  const after = event.after?.state;
  if (before && after) return `${humanise(before)} -> ${humanise(after)}`;
  if (event.after && typeof event.after === "object") {
    return Object.entries(event.after)
      .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)
      .join(", ");
  }
  return "";
}

function row(event) {
  return h(
    "tr",
    {},
    h("td", { class: "num mono" }, String(event.seq)),
    h("td", { class: "num" }, formatDateTime(event.occurred_at)),
    h("td", {}, event.actor_name ?? event.actor_id),
    h("td", {}, h("code", {}, event.action)),
    h("td", {}, h("div", {}, humanise(event.entity_type)), h("div", { class: "sub small" }, change(event))),
    h("td", {}, event.reason ?? ""),
  );
}

async function loadPage() {
  const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (oldestSeq !== null) query.set("before_seq", String(oldestSeq));
  const events = await api(`/api/projects/${encodeURIComponent(projectId)}/audit?${query}`);
  if (tbody === null) {
    if (events.length === 0) {
      document.getElementById("events").replaceChildren(h("p", { class: "empty" }, "No audit entries."));
      return;
    }
    tbody = h("tbody", {});
    document.getElementById("events").replaceChildren(
      h(
        "table",
        { class: "table" },
        h("thead", {}, h("tr", {}, ["#", "When", "Who", "Action", "What changed", "Reason"].map((label) => h("th", {}, label)))),
        tbody,
      ),
    );
  }
  tbody.append(...events.map(row));
  if (events.length) oldestSeq = events[events.length - 1].seq;
  document.getElementById("older").hidden = events.length < PAGE_SIZE;
}

function enableVerify() {
  const button = document.getElementById("verify");
  const result = document.getElementById("verify-result");
  button.hidden = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const outcome = await api("/api/audit/verify");
      result.className = outcome.ok ? "alert alert-success" : "alert alert-error";
      result.textContent = outcome.ok
        ? `Hash chain intact: ${outcome.events_checked} events verified across all projects.`
        : `Hash chain BROKEN at event #${outcome.first_broken_seq} (${outcome.events_checked} events verified before it).`;
    } catch (failure) {
      result.className = "alert alert-error";
      result.textContent = failure.message;
    } finally {
      result.hidden = false;
      button.disabled = false;
    }
  });
}

startPage(async (me) => {
  if (!projectId) throw new Error("No project selected");
  const detail = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  const link = document.getElementById("project-link");
  link.textContent = detail.project.name;
  link.href = `project.html?id=${encodeURIComponent(projectId)}`;
  if (me.is_platform_admin) enableVerify();
  document.getElementById("older").addEventListener("click", () => loadPage());
  await loadPage();
});
