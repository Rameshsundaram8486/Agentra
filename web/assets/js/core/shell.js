/* Page bootstrap: loads the signed-in user, renders the header, and reports load errors. */

import { api } from "./api.js";
import { errorAlert, h } from "./format.js";

export function param(name) {
  return new URLSearchParams(location.search).get(name);
}

function renderShell(me) {
  const signOut = h(
    "button",
    {
      class: "button button-quiet",
      type: "button",
      onclick: async () => {
        await api("/api/auth/logout", { method: "POST" }).catch(() => null);
        location.assign("login.html");
      },
    },
    "Sign out",
  );
  document.getElementById("shell").replaceChildren(
    h("a", { class: "brand", href: "projects.html" }, "Agentra"),
    h("nav", { class: "nav" }, h("a", { href: "projects.html" }, "Projects")),
    h("div", { class: "who" }, h("span", {}, me.display_name), me.is_platform_admin ? h("span", { class: "tag" }, "admin") : null, signOut),
  );
}

/** Runs a page: signs-in check, header, then render(me). Errors replace the page content. */
export async function startPage(render) {
  const main = document.querySelector("main");
  try {
    const me = await api("/api/auth/me");
    renderShell(me);
    await render(me);
  } catch (error) {
    if (error?.status === 401) return; // api() is already redirecting to sign-in
    main.replaceChildren(errorAlert(error));
  }
}
