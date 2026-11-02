/* Page script: Sign-in page. */

import { api } from "../../core/api.js";

const form = document.getElementById("login-form");
const error = document.getElementById("login-error");
const button = form.querySelector("button[type=submit]");

/** Only return to pages inside the Control Center, never to another site. */
function nextPage() {
  const next = new URLSearchParams(location.search).get("next");
  return next && next.startsWith("/app/control-center/") && !next.includes("//") ? next : "projects.html";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.hidden = true;
  button.disabled = true;
  try {
    await api("/api/auth/login", { method: "POST", body: { email: form.email.value, password: form.password.value } });
    location.assign(nextPage());
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
    form.password.select();
  } finally {
    button.disabled = false;
  }
});
