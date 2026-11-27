// Accessibility and layout audit of the Command Center demo, page by page, in both themes and at several widths.
// Drives headless Edge or Chrome over the DevTools protocol (Node 22+, no packages). For each page it checks:
//   overflow  - the page scrolls sideways
//   names     - buttons, links and form controls without an accessible name (from the browser's accessibility tree)
//   heading   - not exactly one h1
//   contrast  - text below WCAG AA (4.5:1, or 3:1 for large text) against its real background
//   focus     - Tab does not move focus, or the focused element shows no focus indicator
//   errors    - JavaScript exceptions or console errors
// Usage: node scripts/audit.mjs <base-url> <route>[,<route>...] [--widths=1366,390] [--themes=dark,light] [--tabs=12]
// Exits 1 when it finds problems; prints them grouped by page.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [base, routeArg = "/", ...flags] = process.argv.slice(2);
const option = (name, fallback) => flags.find((f) => f.startsWith(`--${name}=`))?.split("=")[1].split(",") ?? fallback;
const routes = routeArg.split(",");
const widths = option("widths", ["1366", "390"]).map(Number);
const themes = option("themes", ["dark", "light"]);
const tabs = Number(option("tabs", ["12"])[0]);
const HEIGHTS = { 1920: 1080, 1366: 900, 820: 1180, 390: 844 };
const browserExe = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].find(existsSync);
if (!base || !browserExe) {
  console.error("usage: node scripts/audit.mjs <base-url> <routes> [--widths=1366,390] [--themes=dark,light]; needs Edge or Chrome");
  process.exit(2);
}

const port = 9335;
const profile = mkdtempSync(join(tmpdir(), "agentra-audit-"));
const browser = spawn(browserExe, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
let nextId = 1;
const pending = new Map();
let pageErrors = [];

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

/* Checks that run inside the page ---------------------------------------------------------------- */

const CONTRAST = `(() => {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const rgba = (css) => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = "rgba(0,0,0,0)";
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  };
  const over = (top, bottom) => { const a = top[3]; return [0, 1, 2].map((i) => top[i] * a + bottom[i] * (1 - a)).concat(1); };
  const lum = ([r, g, b]) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const background = (el) => {
    const layers = [];
    for (let node = el; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.backgroundImage !== "none") return null; // images and gradients: cannot judge reliably
      const color = rgba(style.backgroundColor);
      if (color[3] > 0) layers.push(color);
      if (color[3] >= 1) break;
    }
    let result = rgba(getComputedStyle(document.body).backgroundColor);
    for (const layer of layers.reverse()) result = over(layer, result);
    return result;
  };
  const failures = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    const el = text.parentElement;
    if (!el || seen.has(el) || !text.textContent.trim()) continue;
    seen.add(el);
    if (el.closest("[aria-hidden=true], .sr-only, svg, :disabled, [aria-disabled=true], .recharts-wrapper, [role=log]")) continue;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (rect.width === 0 || rect.height === 0 || style.visibility === "hidden") continue;
    let opacity = 1;
    for (let node = el; node; node = node.parentElement) opacity *= Number(getComputedStyle(node).opacity);
    if (opacity < 0.95) continue; // faded on purpose (e.g. pages behind a dialog)
    if (rgba(style.color)[3] === 0) continue; // text painted by a background (background-clip: text)
    const bg = background(el);
    if (!bg) continue;
    const fg = over(rgba(style.color), bg);
    const size = parseFloat(style.fontSize);
    const bold = Number(style.fontWeight) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const value = ratio(fg, bg);
    if (value < (large ? 3 : 4.5)) failures.push({ text: text.textContent.trim().slice(0, 40), ratio: Math.round(value * 100) / 100, size, color: style.color });
  }
  return failures;
})()`;

const PAGE = `(() => ({
  overflow: document.documentElement.scrollWidth - window.innerWidth,
  h1: document.querySelectorAll("h1").length,
}))()`;

const FOCUS = `(() => {
  const el = document.activeElement;
  if (!el || el === document.body) return { tag: "body" };
  const style = getComputedStyle(el);
  const visible = (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
  const label = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || el.tagName).trim().replace(/\\s+/g, " ").slice(0, 40);
  return { tag: el.tagName.toLowerCase(), label, visible };
})()`;

const INTERACTIVE = new Set(["button", "link", "checkbox", "radio", "combobox", "textbox", "searchbox", "tab", "menuitem", "switch", "slider", "spinbutton", "option"]);

async function unnamed() {
  const { nodes } = await send("Accessibility.getFullAXTree");
  const found = nodes.filter((n) => !n.ignored && INTERACTIVE.has(n.role?.value) && !(n.name?.value ?? "").trim());
  const out = [];
  for (const n of found) {
    let html = "";
    try {
      html = (await send("DOM.getOuterHTML", { backendNodeId: n.backendDOMNodeId })).outerHTML.replace(/\s+/g, " ").slice(0, 140);
    } catch {}
    out.push(`${n.role.value} ${html}`);
  }
  return out;
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
      pageErrors.push(`JS exception: ${message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text}`);
    } else if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
      pageErrors.push(`console.error: ${message.params.args.map((a) => a.value ?? a.description).join(" ")}`);
    }
  };
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Accessibility.enable");
  await send("DOM.enable");

  const report = [];
  for (const theme of themes) {
    for (const width of widths) {
      for (const route of routes) {
        pageErrors = [];
        await send("Emulation.setDeviceMetricsOverride", { width, height: HEIGHTS[width] ?? 900, deviceScaleFactor: 1, mobile: width < 600 });
        await send("Page.navigate", { url: "about:blank" });
        await sleep(150);
        await send("Storage.clearDataForOrigin", { origin: new URL(base).origin, storageTypes: "local_storage" });
        await send("Page.navigate", { url: `${base}/?theme=${theme}#${route}` });
        await waitFor(`document.documentElement.dataset.theme === "${theme}" && !!document.querySelector("main h1, [role=dialog] h2")`, `${route} in ${theme}`).catch(async (e) => { console.error(await evaluate("location.href + \" | theme=\" + document.documentElement.dataset.theme + \" | \" + document.body.innerText.slice(0, 200)")); throw e; });
        // Headless browsers do not advance CSS transitions between frames, so colours can be stale after the theme
        // switch; turn transitions off and measure the final styles.
        await evaluate("(() => { const s = document.createElement('style'); s.textContent = '*, *::before, *::after { transition: none !important; animation: none !important; }'; document.head.appendChild(s); return true; })()");
        await sleep(700);
        const problems = [];
        const page = await evaluate(PAGE);
        if (page.overflow > 1) problems.push(`overflow: scrolls ${page.overflow}px sideways`);
        if (page.h1 !== 1 && !route.includes("?id=")) problems.push(`heading: ${page.h1} h1 elements`);
        const names = await unnamed();
        for (const n of names) problems.push(`names: no accessible name: ${n}`);
        for (const f of await evaluate(CONTRAST)) problems.push(`contrast ${f.ratio}:1 "${f.text}" (${f.size}px, ${f.color})`);
        // Keyboard: Tab through the start of the page.
        await evaluate("document.activeElement?.blur(), window.scrollTo(0, 0), true");
        const focused = [];
        for (let i = 0; i < tabs; i++) {
          await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
          await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
          await sleep(40);
          focused.push(await evaluate(FOCUS));
        }
        if (focused.every((f) => f.tag === "body")) problems.push("focus: Tab does not move focus");
        for (const f of focused.filter((x) => x.tag !== "body" && !x.visible)) problems.push(`focus: no visible indicator on <${f.tag}> "${f.label}"`);
        problems.push(...pageErrors);
        const unique = [...new Set(problems)];
        report.push({ route, theme, width, problems: unique });
        console.log(`${unique.length ? "✗" : "✓"} ${route} ${theme} ${width}${unique.length ? `: ${unique.length} problem(s)` : ""}`);
        for (const p of unique.slice(0, 12)) console.log(`    ${p}`);
        if (unique.length > 12) console.log(`    … ${unique.length - 12} more`);
      }
    }
  }
  const failing = report.filter((r) => r.problems.length);
  console.log(`\n${report.length - failing.length} of ${report.length} page views clean.`);
  return failing.length ? 1 : 0;
}

main()
  .then((code) => { browser.kill(); process.exit(code); })
  .catch((error) => { console.error(error); browser.kill(); process.exit(2); });
