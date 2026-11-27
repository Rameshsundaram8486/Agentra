# ADR 0005 — Command Center demo frontend in React

- **Status:** Accepted (2026-11-26)
- **Exception to:** the stack rule "plain HTML/CSS/JS in `web/`" (CLAUDE.md), for the demo only.

## Decision
The interactive Agentra Command Center demo (13 screens for executive, customer and investor presentations) is a separate React + TypeScript application in `HTML/`, built with Vite: Tailwind CSS, Lucide icons, Recharts, React Flow (`@xyflow/react`), Radix UI primitives, zustand, Vitest. It runs on simulated data from a scripted, deterministic scenario and makes no backend calls. Pages read data only through a `DataService` interface, so an API-backed implementation can replace the demo one later.

## Consequences
- `web/` stays the real, governed Control Center; its strict Content-Security-Policy is unchanged. The demo is served on its own (Vite), not by the API, because chart and graph libraries need inline styles.
- The demo must never pass for real operation: a permanent "Demo, simulated data" badge, simulated controls labelled as such, fictional customers only.
- The Model Gateway screen shows the Claude API as the only live provider (ADR 0001); Ollama and cloud GPU appear only as unconfigured options. Phases outside the MVP (1–6, 12–13) appear as labelled previews.
- `HTML/node_modules` and `HTML/dist` are not committed.
