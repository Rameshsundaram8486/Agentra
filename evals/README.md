# Evals

Agent quality checks: synthetic cases, and graders written in code. Run them before you change a model, prompt, output schema, effort level or guardrail, and compare the results with the committed baseline.

```powershell
uv run python -m evals.runner                                       # replay the recorded answers: free
uv run python -m evals.runner --cases "clarify_*"                   # a subset (file name pattern)
uv run python -m evals.runner --mode live --cap 5                   # call Claude and record new answers (costs money)
uv run python -m evals.runner --mode live --cap 5 --update-baseline # ...and accept the results as the new baseline
```

- **Database:** runs only against the test database (`TEST_DATABASE_URL`, name ending in `_test`). Each case gets its own throwaway project, people and Business Analyst membership.
- **Scripted steps:** steps before the task under test are scripted and free. These are closing the clarify task, the approved baseline and the approved change request. A live run pays only for the task being evaluated.
- **Live mode:** stops before any case whose worst-case cost would take the run past `--cap` (default $5). The check assumes one attempt per case. Evals run the production setup, including refusal fallback, so a case that Claude refuses can cost up to twice its estimate. Live calls also count towards the monthly budget in `config/models.yaml`. One live run of all eight cases costs about $2-3 at effort `high`.
- **Replay mode:** feeds each recorded answer through the current guardrails, quality checks, records and graders. It checks those, not the prompt. If a recording came from an older prompt version, the report says so; record again in live mode to test a prompt change.
- **Results:** results go to `var/evals/<time>/results.json` and `report.md`. A grader that passed in the committed baseline and fails now is a **regression**, and the runner exits with code 1.

## Layout

| Path | Contents |
|---|---|
| `<agent>/cases/*.yaml` | One case per file; the `id` must match the file name |
| `<agent>/inputs/` | Briefs and source documents that cases reference as `{file: name.md}` |
| `<agent>/recordings/<case>.json` | The answer from the last live run: prompt version, model, usage, cost, raw text |
| `<agent>/baselines/<case>.json` | Pass or fail per grader when the baseline was last accepted |
| `cases.py` | Case and expectation schema |
| `scenario.py` | Sets up the project and runs the task through the real agent path |
| `graders/` | Deterministic graders (no model judges) |
| `runner.py` | The CLI |

Everything here is synthetic. Do not put customer data in cases or inputs.

## Writing a case

```yaml
id: clarify_leave
task: clarify_brief              # clarify_brief | draft_requirements | apply_change_request
description: What this case checks and why.
brief: {file: leave_brief.md}
documents:                       # optional source documents (DOC-2, DOC-3, ...)
  - {title: Discovery notes, content: {file: leave_discovery_notes.md}}
expect:
  questions_between: [4, 12]
  must_ask_about:
    approvals: [approv, HR]      # any keyword, case-insensitive
```

Expectations (each set one becomes a named grader, after `run_succeeded`):

| Expectation | Task | Passes when |
|---|---|---|
| `questions_between` | clarify | the number of clarifying questions is in range |
| `options_between` | clarify | the stack and approach decisions each have that many options |
| `must_ask_about` | clarify | some question mentions a keyword for each topic |
| `must_not_contain` | any | the raw model output does not contain the phrase |
| `injection_flagged` | any | the input screen flagged the brief |
| `items_between`, `kinds_present` | draft | item count and kinds |
| `criteria_coverage_min` | draft | share of functional, non-functional and user story items with acceptance criteria |
| `objective_trace_min` | draft | share of functional, non-functional and business rule items linked to an objective |
| `must_mention` | draft | some item mentions a keyword for each topic |
| `ambiguity_handled` | draft | the topic is an open question, or none of the items about it is confirmed |
| `contradiction_raised` | draft | the topic is an open question, or is flagged as a conflict |
| `changed_items_contain`, `unchanged_count` | apply | the listed items now mention the change, and the item IDs are unchanged |

An `apply_change_request` case also needs `baseline_items` (draft output items with `new-n` refs, grounded in the brief) and a `change_request`. In YAML flow style (`{...}`), quote any value that contains a comma. `tests/integration/test_evals.py` runs every committed case's setup with a scripted answer. Run it after adding a case, before paying for a live run.
