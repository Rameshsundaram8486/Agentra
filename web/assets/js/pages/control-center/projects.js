/* Page script: Projects list and (for platform admins) project creation. */

import { api } from "../../core/api.js";
import { control, formatDateTime, h } from "../../core/format.js";
import { startPage } from "../../core/shell.js";

function renderList(projects) {
  const container = document.getElementById("project-list");
  if (projects.length === 0) {
    container.replaceChildren(h("p", { class: "empty" }, "No projects yet."));
    return;
  }
  const rows = projects.map((project) =>
    h(
      "tr",
      {},
      h("td", {}, h("a", { class: "primary", href: `project.html?id=${encodeURIComponent(project.id)}` }, project.name), h("div", { class: "sub mono" }, project.code)),
      h("td", {}, project.customer_name),
      h("td", { class: "num" }, formatDateTime(project.created_at)),
    ),
  );
  container.replaceChildren(
    h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "Project"), h("th", {}, "Customer"), h("th", {}, "Created"))), h("tbody", {}, rows)),
  );
}

function enableCreation() {
  const toggle = document.getElementById("new-project-toggle");
  const section = document.getElementById("new-project");
  const form = document.getElementById("new-project-form");
  const error = document.getElementById("new-project-error");
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    section.hidden = false;
    toggle.hidden = true;
    form.code.focus();
  });
  document.getElementById("new-project-cancel").addEventListener("click", () => {
    section.hidden = true;
    toggle.hidden = false;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    try {
      const project = await api("/api/projects", {
        method: "POST",
        body: {
          code: form.code.value.trim(),
          name: control(form, "name").value.trim(),
          customer_name: form.customer_name.value.trim(),
          description: form.description.value.trim() || null,
        },
      });
      location.assign(`project.html?id=${encodeURIComponent(project.id)}`);
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    }
  });
}

startPage(async (me) => {
  if (me.is_platform_admin) enableCreation();
  renderList(await api("/api/projects"));
});
