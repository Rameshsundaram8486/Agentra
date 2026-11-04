/* Page script: Report viewer - provenance of one report version and the rendered document in a sandboxed frame. */

import { api } from "../../core/api.js";
import { formatDateTime, h } from "../../core/format.js";
import { param, startPage } from "../../core/shell.js";

const reportId = param("id");

function row(label, value) {
  return [h("dt", {}, label), h("dd", {}, value)];
}

startPage(async () => {
  if (!reportId) throw new Error("No report selected");
  const report = await api(`/api/reports/${encodeURIComponent(reportId)}`);
  const html = `/api/reports/${encodeURIComponent(report.id)}/html`;
  document.title = `${report.title} v${report.version_no} - Agentra`;
  document.getElementById("report-title").textContent = `${report.title} v${report.version_no}`;
  document.getElementById("back-link").href = `project.html?id=${encodeURIComponent(report.project_id)}`;
  document.getElementById("report-meta").textContent = `Generated ${formatDateTime(report.generated_at)} by ${report.generated_by_name ?? "unknown"}`;
  document.getElementById("printable").href = html;
  document.getElementById("data-link").href = `/api/reports/${encodeURIComponent(report.id)}/data`;
  document.getElementById("provenance").replaceChildren(
    ...row("Data as of", report.data_as_of ? formatDateTime(report.data_as_of) : "No records yet"),
    ...row("Visible to customers", report.customer_visible ? "Yes" : "No (internal)"),
    ...row("Data hash", h("span", { class: "hash" }, report.data_sha256)),
    ...row("Document hash", h("span", { class: "hash" }, report.content_sha256)),
    ...row("Template version", h("span", { class: "hash" }, report.template_version)),
    ...row("Sources", h("ul", { class: "bullets small" }, report.sources.map((source) => h("li", {}, source)))),
  );
  document.getElementById("report-frame").src = html;
});
