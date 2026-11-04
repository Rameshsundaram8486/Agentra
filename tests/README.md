# Tests

| Folder | Contents |
|---|---|
| `unit/` | Domain rules and infrastructure helpers; no database |
| `integration/` | Real PostgreSQL test database (`TEST_DATABASE_URL`, name must end in `_test`) |
| `workflow/` | Phase state transitions, success and rejected paths (from Increment 1a) |
| `security/` | Authorisation, self-approval, version mismatch, who may start agent runs |
| `live/` | Real Claude API calls; skipped unless `AGENTRA_LIVE_TESTS=1` (they cost money) |
| `unit/evals/`, `integration/test_evals.py` | The evals harness (`evals/`): case loading, graders, replay, regressions, the spending cap, and setup of every committed case |
| `e2e/` | Synthetic project through Phases 7 to 11 (Increment 10) |

Run everything with `uv run pytest`. Shared fixtures live in `conftest.py`; agent tests use `FakeProvider` (`app/model_gateway/providers/fake.py`) and the synthetic brief in `agent_support.py`.
