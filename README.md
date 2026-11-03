# Agentra — A Company Runs by Agents

AI-native operating platform for an IT services company. Specialised agents do bounded work, a workflow engine owns state, and humans approve consequential decisions against exact artifact versions.

> **Status: Increment 1b (artifacts, decisions, approvals) done.** Working so far:
> - sign-in with server sessions
> - projects and role-based memberships
> - a workflow engine driven by YAML lifecycles, with entry and exit gates, optimistic locking and a record of every transition
> - an append-only, hash-chained audit trail
> - a job queue and transactional outbox
> - versioned documents stored by content hash, with diffs
> - approvals bound to the exact version and hash, with no self-approval and never by agents
> - decision records that keep the original recommendation
> - phase completion gated on approvals
> - the Control Center pages for projects, documents, decisions and the audit trail
>
> Everything else is still scaffold: those files carry a one-line purpose header and say "Scaffold only". See [docs/architecture/overview.md](docs/architecture/overview.md).

## Getting started

See [docs/development-guide.md](docs/development-guide.md). In short: `scripts\create_db.ps1`, then `scripts\dev_setup.ps1`, then `scripts\run_api.ps1`. Run tests with `uv run pytest`.

## Where things are

| Path | Contents |
|---|---|
| `Product Docs/` | Product vision, overview, phase specs (01–13), cross-cutting specs, architecture images |
| `docs/` | Engineering docs: architecture, decision records (`adr/`), development guide |
| `config/` | Declarative, versioned config: agents, phase workflows, policies, model routing |
| `app/api/` | FastAPI routers only, no business logic |
| `app/modules/` | Bounded contexts (domain + repository + service), one per business area |
| `app/modules/workflow/` | Authoritative state machine, gates, readiness, dispatch |
| `app/harness/` | Agent runtime: agent loop, context, tools, sandbox VM control |
| `app/guardrails/` | Deterministic input / tool / output checks around every agent run |
| `app/model_gateway/` | Provider-neutral model access (Claude API provider) |
| `app/agents/` | Thin phase-specific agent logic (definitions live in `config/agents/`) |
| `app/integrations/` | Microsoft 365, Power Platform, Azure, Git, voice, documents |
| `app/infrastructure/` | DB, job queue, outbox, storage, secrets, logging |
| `app/workers/` | Background processes: workflow worker, outbox, oversight monitor, reports, sandbox reaper |
| `web/` | Control Center (`control-center/`) and Customer Portal (`portal/`): HTML, CSS, JS |
| `sandbox-agent/` | Small service inside sandbox VMs (commands, screenshots, mouse/keyboard) |
| `infra/` | VM images (Packer), network rules, Azure (Bicep), local Hyper-V and PostgreSQL setup |
| `migrations/` | Alembic migrations (PostgreSQL) |
| `evals/` | Golden cases and graders per agent |
| `tests/` | unit, workflow, security, integration, e2e |
| `scripts/` | Local setup and run scripts |

## Key decisions

See `docs/adr/`: Claude API as model provider, PostgreSQL from day one, sandbox VMs for code execution, computer use inside VMs only.

## Delivery order

MVP first: Phases 7 → 11 plus Project Owner, reporting and governance. Phases 1–6 and 12–13 follow after MVP acceptance. Their folders exist now so boundaries are fixed early; they stay empty until then.
