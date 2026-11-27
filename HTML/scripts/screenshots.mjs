// Screenshots of the Command Center demo in both themes at several widths, for the review after each build stage.
// Drives headless Edge or Chrome over the DevTools protocol (Node 22+, no packages); fails on JS errors.
// Usage: node scripts/screenshots.mjs <base-url> <out-dir> <route>[,<route>...] [--live] [--widths=1920,1366,820] [--themes=dark,light]
//   A route may end with "@<javascript>" to run before the shot (e.g. open a menu): /@document.querySelector('...').click()
//   e.g. node scripts/screenshots.mjs http://127.0.0.1:4173 ../var/demo-screens/stage1 / --live
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const [base, outDir, routeArg = "/", ...flags] = process.argv.slice(2);
/** Splits on commas outside brackets and quotes, so an action may contain commas. */
function splitTopLevel(text) {
  const parts = [];
  let depth = 0;
  let quote = null;
  let current = "";
  for (const ch of text) {
    if (quote) {
      if (ch === quote) quote = null;
    } else if (ch === "'" || ch === '"') quote = ch;
    else if ("([{".includes(ch)) depth += 1;
    else if (")]}".includes(ch)) depth -= 1;
    else if (ch === "," && depth === 0) {
      parts.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  parts.push(current);
  return parts;
}

const routes = splitTopLevel(routeArg).map((spec) => {
  const at = spec.indexOf("@");
  return at < 0 ? { route: spec, action: null } : { route: spec.slice(0, at), action: spec.slice(at + 1) };
});
const live = flags.includes("--live");
const option = (name, fallback) => flags.find((f) => f.startsWith(`--${name}=`))?.split("=")[1].split(",") ?? fallback;
const widths = option("widths", ["1920", "1366", "820"]).map(Number);
const themes = option("themes", ["dark", "light"]);
const HEIGHTS = { 1920: 1080, 1366: 900, 820: 1180, 390: 844 };
const browserExe = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].find(existsSync);
if (!base || !outDir || !browserExe) {
  console.error("usage: node scripts/screenshots.mjs <base-url> <out-dir> <routes> [--live]; needs Edge or Chrome");
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });

const port = 9334;
const browser = spawn(browserExe, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${resolve(outDir, "..", ".browser-profile")}`, "--no-first-run", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [];
let ws;
let nextId = 1;
const pending = new Map();

function send(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject, method }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}

async function waitFor(expression, what, timeout = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await evaluate(expression)) return;
    } catch {}
    await sleep(150);
  }
  throw new Error(`timed out waiting for ${what}`);
}

async function main() {
  let url;
  for (let i = 0; i < 150 && !url; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      url = targets.find((t) => t.type === "page")?.webSocketDebuggerUrl;
    } catch {}
    if (!url) await sleep(200);
  }
  if (!url) throw new Error("the browser did not start");
  ws = new WebSocket(url);
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
    }
  };
  await send("Page.enable");
  await send("Runtime.enable");

  for (const theme of themes) {
    for (const width of widths) {
      const height = HEIGHTS[width] ?? 900;
      for (const [index, { route, action }] of routes.entries()) {
        await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
        // A fresh demo for each shot: leave the page (so it stops saving), clear its saved state, then load with the theme.
        await send("Page.navigate", { url: "about:blank" });
        await sleep(200);
        await send("Storage.clearDataForOrigin", { origin: new URL(base).origin, storageTypes: "local_storage" });
        await send("Page.navigate", { url: `${base}/?theme=${theme}#${route}` });
        await waitFor(`document.documentElement.dataset.theme === '${theme}' && document.querySelector('#root')?.children.length > 0`, `${route} in ${theme}`);
        if (live) {
          // Start the simulation from the demo controls in the top bar (every page has them).
          await evaluate("document.querySelector('[aria-label^=\"Simulation paused\"]')?.click(), true");
          await sleep(400);
          await evaluate("[...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Start simulation')?.click(), true");
          await sleep(300);
          await evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })), true");
          await sleep(9000); // nine simulation ticks
        } else {
          await sleep(600);
        }
        if (action) {
          await evaluate(`(${action}, true)`);
          await sleep(700);
        }
        if (!action) {
          // Grow the window to the whole page, so sticky bars stay at the top of a full-page shot.
          const full = await evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)");
          await send("Emulation.setDeviceMetricsOverride", { width, height: Math.max(height, full), deviceScaleFactor: 1, mobile: false });
          await sleep(500);
        }
        const { data } = await send("Page.captureScreenshot", { format: "png" });
        const stem = route.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "home";
        const name = `${stem}${action ? `-action${index}` : ""}-${theme}-${width}.png`;
        writeFileSync(join(outDir, name), Buffer.from(data, "base64"));
        console.log(`saved ${name}`);
      }
    }
  }
}

main()
  .catch((error) => problems.push(`failed: ${error.message}`))
  .finally(() => {
    browser.kill();
    if (problems.length) {
      console.error(problems.join("\n"));
      process.exit(1);
    }
    console.log("no JS errors");
  });
