# Development guide

Local setup, running and testing on Windows. No Docker.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Windows 11 Pro | 24H2+ | Pro is needed for Hyper-V (sandbox VMs, from Increment 5) |
| uv | latest | `winget install astral-sh.uv`; manages Python 3.12 and dependencies |
| PostgreSQL | 16+ (18 in use) | Native Windows install, service running on port 5432 |
| git | any recent | |

Python itself does not need to be installed separately: `uv` provides 3.12 (pinned in `.python-version`).

## First-time setup

```powershell
# 1. Create the agentra role and the agentra_dev / agentra_test databases; writes the URLs into .env
powershell -ExecutionPolicy Bypass -File scripts\create_db.ps1

# 2. Install dependencies into .venv and migrate the development database
powershell -ExecutionPolicy Bypass -File scripts\dev_setup.ps1
```

`create_db.ps1` asks for the postgres superuser password (or reads `$env:PGPASSWORD`) and never stores it. The `agentra` role gets a random password that is written only to `.env`, which is gitignored. The role is not a superuser and cannot create databases or roles.

## Running

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_api.ps1   # http://127.0.0.1:8000, auto-reload
```

- `GET /health` returns `200 {"status": "ok", "database": "ok", ...}`, or `503` with `"database": "unavailable"`.
- API docs at `/docs` (disabled when `AGENTRA_ENV=production`).

## Testing

```powershell
uv run pytest            # all tests
uv run pytest tests\unit # unit tests only, no database needed
```

- Integration tests use `TEST_DATABASE_URL` from `.env`, and refuse to run unless the database name ends in `_test`.
- Tests run against real PostgreSQL, not SQLite or mocks (ADR 0002).

## Database migrations

```powershell
uv run alembic upgrade head                                            # apply
uv run alembic revision --autogenerate --rev-id 0002 -m "describe change"  # create
```

- The database URL comes from `.env` (via `app/infrastructure/settings.py`), never from `alembic.ini`.
- `tests/integration/test_migrations.py` fails if the SQLAlchemy models and the migrations drift apart, and checks that every migration downgrades cleanly.

## Conventions

- **Settings:** `app/infrastructure/settings.py` is the only place that reads environment variables. Secrets are `SecretStr`, so they never appear in `repr` or dumps.
- **Logging:** use `logging.getLogger(__name__)` and pass context with `extra={...}`. Output is one JSON object per line. Connection-string passwords, API keys, bearer tokens, `password=`/`token=` pairs and every configured secret value are masked when the line is written, including inside tracebacks.
- **Transactions:** wrap work in `UnitOfWork`. Nothing is saved unless `commit()` is called explicitly; leaving the block, or an exception, rolls back.
- **Dependencies:** add with `uv add <package>` (or `uv add --dev`), and commit `uv.lock`.
- **Data:** use synthetic data locally only.
