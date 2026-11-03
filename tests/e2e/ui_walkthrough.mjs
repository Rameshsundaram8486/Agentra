// Browser walkthrough of the Control Center: drives headless Edge or Chrome over the Chrome DevTools Protocol
// (Node 22+, no npm packages). Fails on any failed step, JS exception or console error; saves screenshots.
// Run it with scripts/run_ui_walkthrough.ps1, which uses the TEST database, never the development one.
// Usage: node ui_walkthrough.mjs <base-url> <seed.json> <out-dir> <browser-exe>
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [base, seedPath, outDir, browserExe] = process.argv.slice(2);
const seed = JSON.parse(readFileSync(seedPath, "utf8"));
mkdirSync(outDir, { recursive: true });
const port = 9333;
const browser = spawn(browserExe, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${join(outDir, "profile")}`,
  "--no-first-run", "--no-default-browser-check", "--window-size=1366,900", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, nextId = 1;
const pending = new Map();
const problems = [];
const steps = [];

async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(200);
  }
  throw new Error("browser did not start");
}

function send(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject, method }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`evaluate failed: ${result.exceptionDetails.exception?.description ?? result.exceptionDetails.text}`);
  return result.result.value;
}

async function waitFor(expression, what, timeout = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try { if (await evaluate(expression)) return; } catch {}
    await sleep(150);
  }
  const body = await evaluate("document.body ? document.body.innerText.slice(0, 600) : ''").catch(() => "");
  throw new Error(`timed out waiting for: ${what}\n--- page text ---\n${body}`);
}

async function goto(path, readyExpression, what) {
  await send("Page.navigate", { url: base + path });
  await waitFor(`document.readyState === 'complete'`, `load ${path}`);
  await waitFor(readyExpression, what);
}

async function shot(name) {
  const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(join(outDir, `${name}.png`), Buffer.from(data, "base64"));
}

const js = (value) => JSON.stringify(value);
function fill(selector, value) {
  return evaluate(`(() => { const el = document.querySelector(${js(selector)}); el.value = ${js(value)}; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); return true; })()`);
}
async function setFile(selector, path) {
  const { root } = await send("DOM.getDocument", { depth: 0 });
  const { nodeId } = await send("DOM.querySelector", { nodeId: root.nodeId, selector });
  await send("DOM.setFileInputFiles", { nodeId, files: [path] });
  await evaluate(`(document.querySelector(${js(selector)}).dispatchEvent(new Event('change', {bubbles: true})), true)`);
}
const click = (selector) => evaluate(`(document.querySelector(${js(selector)}).click(), true)`);
const text = (selector) => evaluate(`document.querySelector(${js(selector)})?.innerText ?? ''`);

async function step(name, fn) {
  try {
    await fn();
    steps.push(`PASS  ${name}`);
  } catch (error) {
    steps.push(`FAIL  ${name}: ${error.message}`);
    await shot(`FAILED-${name.replace(/[^a-z0-9]+/gi, "-")}`).catch(() => {});
    throw error;
  }
}

async function login(who) {
  await evaluate(`fetch('/api/auth/logout', {method: 'POST'}).then(() => true, () => true)`);
  await goto("/app/control-center/login.html", "!!document.getElementById('login-form')", "login form");
  await fill("#email", seed.users[who]);
  await fill("#password", seed.password);
  await click("#login-form button[type=submit]");
  await waitFor("location.pathname.endsWith('/projects.html') && !!document.querySelector('#shell .brand')", `signed in as ${who}`);
}

async function main() {
  ws = new WebSocket(await connect());
  await new Promise((resolve) => (ws.onopen = resolve));
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject, method } = pending.get(message.id);
      pending.delete(message.id);
      message.error ? reject(new Error(`${method}: ${message.error.message}`)) : resolve(message.result);
    } else if (message.method === "Runtime.exceptionThrown") {
      problems.push(`JS exception: ${message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text}`);
    } else if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
      problems.push(`console.error: ${message.params.args.map((a) => a.value ?? a.description).join(" ")}`);
    } else if (message.method === "Log.entryAdded" && message.params.entry.level === "error" && !/401|409|403/.test(message.params.entry.text)) {
      problems.push(`browser log: ${message.params.entry.text} ${message.params.entry.url ?? ""}`);
    }
  };
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Log.enable");

  const code = `UI-${seed.suffix.toUpperCase()}`;
  let projectUrl, artifactUrl, decisionUrl;

  await step("admin signs in", () => login("admin"));

  await step("admin creates a project (form field named 'name')", async () => {
    await click("#new-project-toggle");
    await fill("#code", code);
    await fill("#name", "UI Intranet");
    await fill("#customer_name", "Example Co");
    await click("#new-project-form button[type=submit]");
    await waitFor("location.pathname.endsWith('/project.html') && document.getElementById('project-name').innerText === 'UI Intranet'", "project page");
    await waitFor("document.querySelectorAll('#phases tbody tr:not([data-task])').length === 5", "five phases");
    projectUrl = await evaluate("location.pathname + location.search");
    await shot("01-project-created");
  });

  await step("phase rows show the approval each phase needs", async () => {
    const phases = await text("#phases");
    if (!phases.includes("Needs approved: Requirements baseline")) throw new Error(phases);
  });

  await step("admin adds the PM, the reviewer and the Business Analyst agent by email", async () => {
    for (const [email, role] of [[seed.users.pm, "project_manager"], [seed.users.reviewer, "reviewer"], [seed.agent, "agent"]]) {
      await fill("#member-email", email);
      await fill("#member-role", role);
      await click("#add-member-form button[type=submit]");
      await waitFor(`document.getElementById('members').innerText.includes(${js(email)})`, `${email} listed`);
    }
  });

  await step("PM creates a requirements baseline (form field named 'title')", async () => {
    await login("pm");
    await goto(projectUrl, "!document.getElementById('new-document-toggle').hidden", "new document button");
    await click("#new-document-toggle");
    await fill("#doc-type", "requirements_baseline");
    await fill("#doc-title", "Leave app BRD");
    await fill("#doc-content", "# Leave app\n\nREQ-F-001: Staff can submit a leave request.\n");
    await fill("#doc-sources", "Project brief p.2, Discovery notes");
    await click("#new-document-form button[type=submit]");
    await waitFor("location.pathname.endsWith('/artifact.html') && document.getElementById('content').innerText.includes('REQ-F-001')", "artifact page with content");
    artifactUrl = await evaluate("location.pathname + location.search");
    await shot("02-document-v1");
  });

  await step("PM adds version 2 and the comparison shows the change", async () => {
    await fill("#nv-content", "# Leave app\n\nREQ-F-001: Staff can submit a leave request.\nREQ-F-002: Managers approve or reject it.\n");
    await fill("#nv-summary", "Added manager approval");
    await click("#new-version-form button[type=submit]");
    await waitFor("document.getElementById('viewing-label').innerText === 'Version 2'", "version 2 shown");
    const meta = await text("#version-meta");
    if (!meta.includes("Project brief p.2")) throw new Error("v2 lost its sources: " + meta);
    await click("#compare");
    await waitFor("document.getElementById('diff').innerText.includes('+REQ-F-002')", "diff with added line");
    await shot("03-document-v2-diff");
  });

  await step("PM cannot approve (not an approver role) and sees the server's reason", async () => {
    await click("#review-panel [data-decision=approved]");
    await waitFor("document.getElementById('review-message').innerText.includes('needs one of these roles')", "permission message");
  });

  await step("reviewer approves version 2", async () => {
    await login("reviewer");
    await goto(artifactUrl, "document.getElementById('viewing-label').innerText === 'Version 2'", "artifact v2");
    await click("#review-panel [data-decision=approved]");
    await waitFor("document.getElementById('approval-status').innerText.toLowerCase().includes('approved')", "approved badge");
    await shot("04-approved");
  });

  await step("PM raises a decision with a recommendation", async () => {
    await login("pm");
    const id = projectUrl.split("id=")[1];
    await goto(`/app/control-center/decisions.html?id=${id}`, "!document.getElementById('raise-toggle').hidden", "raise button");
    await click("#raise-toggle");
    await fill("#d-title", "Intranet platform");
    await fill("#d-question", "Which SharePoint platform should we use?");
    await fill("#d-options", "SharePoint Online - Included in E3\nSubscription Edition - On-premises");
    await fill("#d-recommended", "opt-1");
    await fill("#d-rationale", "Licences already include it.");
    await fill("#d-assumptions", "No on-premises requirement");
    await click("#raise-form button[type=submit]");
    await waitFor("location.pathname.endsWith('/decision.html') && document.querySelector('.recommendation')?.innerText.includes('SharePoint Online')", "decision page");
    decisionUrl = await evaluate("location.pathname + location.search");
  });

  await step("admin chooses 'something else' (radio group named outcome_action)", async () => {
    await login("admin");
    await goto(decisionUrl, "!document.getElementById('decide').hidden", "decide form");
    await click("input[name=outcome_action][value=other]");
    await waitFor("!document.getElementById('other-field').hidden", "other field shown");
    await fill("#custom-choice", "SharePoint Online now, archive on-premises");
    await fill("#comment", "Phased approach");
    await click("#decide-form button[type=submit]");
    await waitFor("document.getElementById('status').innerText.toLowerCase().includes('decided')", "decided");
    const recommendation = await text(".recommendation");
    if (!recommendation.includes("SharePoint Online")) throw new Error("recommendation changed: " + recommendation);
    await shot("05-decision-decided");
  });

  await step("PM starts Phase 7, adds a project brief and asks the Business Analyst agent", async () => {
    await login("pm");
    await goto(projectUrl, "!document.getElementById('agent-section').hidden", "agent panel");
    if (!(await text("#agent-section")).includes("Add a document of type Project brief first")) throw new Error("no-brief hint missing");
    const phase7 = "[...document.querySelectorAll('#phases tbody tr')].find((row) => row.cells[0].innerText.trim() === '7')";
    for (const state of ["ready", "in progress"]) {
      await evaluate(`([...${phase7}.querySelectorAll('button')].find((b) => b.innerText.trim().toLowerCase() === ${js(state)}).click(), true)`);
      await waitFor("document.getElementById('transition-dialog').open", "transition dialog");
      await fill("#transition-reason", "Starting business analysis");
      await click("#transition-form button[type=submit]");
      await waitFor(`!document.getElementById('transition-dialog').open && ${phase7}.querySelector('.badge').innerText.toLowerCase() === ${js(state)}`, `phase 7 ${state}`);
    }
    await click("#new-document-toggle");
    await fill("#doc-type", "project_brief");
    await fill("#doc-title", "Leave app brief");
    await fill("#doc-content", "# Leave app brief\n\nStaff request leave online and managers approve it. The company uses Microsoft 365.\n");
    await click("#new-document-form button[type=submit]");
    await waitFor("location.pathname.endsWith('/artifact.html')", "brief saved");
    await goto(projectUrl, "!document.getElementById('agent-form').hidden", "agent form");
    await click("#agent-submit");
    await waitFor("document.getElementById('agent-runs').innerText.includes('Leave app brief v1')", "run listed");
    const runs = await text("#agent-runs");
    if (!/queued/i.test(runs) || !runs.includes("Waiting for the agent worker")) throw new Error(runs);
    const clarifyRow = "document.querySelector('#phases tr[data-task=clarify_brief]')";
    await waitFor(`${clarifyRow}?.querySelector('.badge').innerText.toLowerCase() === 'in progress'`, "clarify task in progress");
    await click("#agent-submit");
    await waitFor("document.getElementById('agent-error').innerText.includes('already done this task')", "duplicate request notice");
    if (!(await text("#requirements-summary")).includes("Not drafted yet")) throw new Error("requirements section missing");
    await shot("06-agent-run-queued");
  });

  await step("PM uploads a Word file as a source document and its text is extracted", async () => {
    await click("#upload-toggle");
    await setFile("#upload-file", seed.docx);
    await waitFor("document.getElementById('upload-title').value === 'discovery-notes'", "title from file name");
    await fill("#upload-origin", "Emailed by the customer's HR lead");
    await click("#upload-form button[type=submit]");
    await waitFor("location.pathname.endsWith('/artifact.html') && document.getElementById('content').innerText.includes('Leave approvals happen weekly')", "extracted text shown");
    const meta = await text("#version-meta");
    if (!meta.includes("Origin: Emailed by the customer's HR lead")) throw new Error("origin missing: " + meta);
    await shot("07-uploaded-source-document");
  });

  await step("project page lists the approved document and the audit page loads", async () => {
    await goto(projectUrl, "document.getElementById('documents').innerText.includes('Leave app BRD')", "documents table");
    const docs = await text("#documents");
    if (!/approved/i.test(docs)) throw new Error(docs);
    await shot("08-project-overview");
    const id = projectUrl.split("id=")[1];
    await goto(`/app/control-center/audit.html?id=${id}`, "document.querySelectorAll('#events tbody tr').length > 5", "audit rows");
    const audit = await text("#events");
    for (const action of ["approval.record", "artifact.version_add", "decision.outcome", "agent_run.request"]) if (!audit.includes(action)) throw new Error(`audit missing ${action}`);
  });
}

let exitCode = 0;
try {
  await main();
} catch {
  exitCode = 1;
} finally {
  console.log(steps.join("\n"));
  if (problems.length) {
    console.log("--- browser problems ---\n" + [...new Set(problems)].join("\n"));
    exitCode = 1;
  } else {
    console.log("--- no JS exceptions or console errors ---");
  }
  try { ws?.close(); } catch {}
  browser.kill();
  process.exit(exitCode);
}
