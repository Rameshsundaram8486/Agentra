# Tests

| Folder | Contents |
|---|---|
| `unit/` | Domain rules and infrastructure helpers; no database |
| `integration/` | Real PostgreSQL test database (`TEST_DATABASE_URL`, name must end in `_test`) |
| `workflow/` | Phase state transitions, success and rejected paths (from Increment 1a) |
| `security/` | Authorisation, self-approval, version mismatch, prompt injection (from Increment 1a) |
| `e2e/` | Synthetic project through Phases 7 to 11 (Increment 10) |

Run everything with `uv run pytest`. Shared fixtures live in `conftest.py`.
