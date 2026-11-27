# Agentra Command Center (demo)

An interactive demonstration of Agentra as an AI company command center, on **simulated data**. It is not connected to the Agentra backend and never calls it; the real, governed Control Center is in `../web/`. See `../docs/adr/0005-command-center-demo-frontend.md`.

## Run it

```powershell
cd HTML
npm install          # once
npm run dev          # http://127.0.0.1:5173 while developing
npm run build        # type-check and build to dist/
npm run preview      # serve dist/ on http://127.0.0.1:4173
npm test             # unit tests: data consistency, decision rules, simulation
```

Add `?theme=light` or `?theme=dark` to the address to choose the theme.

## How it works

- `src/data/`: one consistent demo world (fictional UAE customers, projects across the 13-phase lifecycle, the 20 agent types of `config/agents/` plus a reporting agent, tasks, runs, decisions, risks, incidents, documents).
- `src/store/`: the store, the actions (human decisions with the real approval rules, execution controls) and the selectors. Health, completion and KPIs are always derived, never stored.
- `src/simulation/`: a scripted, deterministic story. The timeline fires in order; reactions fire when a person has made the decision they depend on. Start, pause, speed and reset are in the demo controls; the state is kept in the browser until reset.
- `src/services/dataService.ts`: the boundary screens use for commands, ready for an API-backed implementation later.
- `scripts/screenshots.mjs`: screenshots in both themes at 1920, 1366 and 820 px for review (`node scripts/screenshots.mjs http://127.0.0.1:4173 ../var/demo-screens/<name> / --live`).
