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

## First user

There is no sign-up page. Create the first platform administrator from the command line; it prompts for a password of at least 12 characters:

```powershell
uv run python -m app.cli create-user --email you@example.com --name "Your Name" --admin
uv run python -m app.cli create-agent --key business_analyst --name "Business Analyst Agent"   # optional
uv run python -m app.cli verify-audit
```

CLI actions are audited as the Agentra system account.

## Running

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_api.ps1   # http://127.0.0.1:8000, auto-reload
```

- `http://127.0.0.1:8000/` opens the Control Center. Sign in, create a project, add members by email, and move phases.
- `GET /health` returns `200 {"status": "ok", "database": "ok", ...}`, or `503` with `"database": "unavailable"`.
- API docs at `/docs` (disabled when `AGENTRA_ENV=production`).

## The Business Analyst agent

Agent runs need the Claude API and a worker process:

1. Put `ANTHROPIC_API_KEY=...` in `.env` (never in source or chat). Use synthetic briefs only until real customer data is approved for this environment (ADR 0001).
2. Start the worker in a second terminal: `powershell -ExecutionPolicy Bypass -File scripts\run_workers.ps1`.
3. `uv run python -m app.cli seed-demo` gives the demo project a synthetic brief and moves Phase 7 to in progress.
4. On the project page, choose **Ask about the brief** and the brief, and click **Ask the Business Analyst agent**. After a minute or two the run shows as succeeded and its questions are in the decision inbox.
5. Answer the questions in the decision inbox, then close the **Clarify the project brief** task in the Phases table (*completed*).
6. Optionally upload source documents (**Upload file**: .txt, .md, .docx or .pdf), then choose **Draft the requirements**. The draft appears under **Requirements** and as the *Business requirements* document; its open questions go to the inbox.
7. Answer them and ask again for a revised draft. A reviewer can also request changes on the document with a comment; asking again then produces a version that answers each comment.
8. Have a reviewer approve the document and complete the draft task. The baseline is now locked.
9. To change it, raise a change request (Requirements section, **Change requests**). An owner and a customer approver, two different people and not the one who raised it, approve it; then **Ask the agent to apply it**. The new version needs approval again. `seed-demo` creates `customer@agentra.local` as the demo customer approver, because `admin@agentra.local` can give only one of the two approvals.

10. Under **Reports**, generate the requirements executive summary or the detailed BRD and traceability report. Each opens in the report viewer; **Open printable version** prints to PDF from the browser. Generating again with nothing changed returns the same version.
11. A failed agent run opens an incident (project page, **Incidents**). Resolve it with a root-cause analysis; someone else verifies and closes it.

12. Phase 8: once the requirements are approved and Phase 7 is completed, start Phase 8, then in the **Agents** panel choose **Solution Architect: compare solution options**, choose an option in Decisions, close the Compare task, and ask for **Solution Architect: draft the design**. The **Solution design** section shows coverage; Phase 8 completes only when every confirmed requirement is covered or excepted.
13. Before the design can be approved, ask for **Security Reviewer: review the design's security** and **Developer: review the design's feasibility** (both work from the current design version). The **Reviews** card under **Solution design** shows what still blocks approval. A high-severity security gap or an item rated not feasible needs a redraft: ask the Solution Architect again, and it must answer every gap and concern; then review the new version. A reviewer signs the security review off by approving it (the checklist is `config/policies/security_checklist.yaml`), then approves the design. The review tasks close once the design is approved.
14. Once the design is approved and the **Draft and review the design** task is closed, ask for **Developer: plan the implementation backlog**. The **Implementation backlog** section lists the work items; an owner, project manager or reviewer approves the backlog document. Phase 8 then completes when every task is closed. Under **Reports**, generate the **design summary** (customers may see it) or the **detailed design pack** (internal).
15. To change an approved design while Phase 8 is open, raise a change request with **Applies to: the solution design** and the design item IDs to change. Agentra shows the requirements and work items they touch. An owner and a reviewer (two different people, not the one who raised it) approve it; then **Ask the Solution Architect to apply it**. The new design version needs its security and feasibility reviews, sign-off and approval again, and the backlog must be replanned and approved (closed tasks can be asked again for the new version).

`seed-demo` also adds tasks defined after a project was opened (for projects from before Increment 3a) and links earlier agent runs to them.

- A security or feasibility review or a backlog plan costs roughly $0.10-0.30; a design redraft that answers review findings can cost $1 or more and take several minutes, because it returns the whole design.
- A clarify run costs roughly $0.15-0.30, and a requirements draft, redraft or applied change request roughly $0.35-0.60 each at effort `high`; the run list shows the cost. `budget.monthly_usd` in `config/models.yaml` (default $50) stops new calls once this month's spend plus the next call's worst case would exceed it.
- Model, effort and token limits per agent are in `config/models.yaml`; the prompt and output schema are in `config/agents/business_analyst/`.

## Testing

```powershell
uv run pytest            # all tests
uv run pytest tests\unit # unit tests only, no database needed
```

- Integration tests use `TEST_DATABASE_URL` from `.env`, and refuse to run unless the database name ends in `_test`.
- Browser walkthrough of the Control Center (headless Edge or Chrome, test database, port 8010): `powershell -ExecutionPolicy Bypass -File scripts\run_ui_walkthrough.ps1`. Screenshots go to `var\ui-walkthrough\screens`.
- Tests run against real PostgreSQL, not SQLite or mocks (ADR 0002).
- Agent tests use a scripted fake model and never call the API. The opt-in live tests make real calls (costs money, about $5 for all seven): `$env:AGENTRA_LIVE_TESTS = "1"; uv run pytest tests\live -s`.
- Agent quality evals (`evals/README.md`): `uv run python -m evals.runner` replays the recorded answers for free and flags regressions against the committed baseline. `--mode live --cap 5` records new answers (costs money; about $2-3 for all cases). Run them before you change a prompt, model, effort level or guardrail.

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
