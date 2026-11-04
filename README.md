# Agentra — A Company Runs by Agents

AI-native operating platform for an IT services company. Specialised agents do bounded work, a workflow engine owns state, and humans approve consequential decisions against exact artifact versions.

> **Status: Increment 4a done: Phase 8 options, solution design and requirement-to-design coverage.** Working so far:
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
> - a model gateway to the Claude API (claude-opus-5-5, effort per agent, refusal fallback, cost per call, a monthly spending cap)
> - guardrails in code around every agent run: secrets redacted and the brief wrapped as data before the call; schema, grounded quotes, no approval claims and no secrets after it
> - the Business Analyst agent: reads a project brief and raises the technology stack, the delivery approach and clarifying questions as decisions for people to answer
> - a background worker for agent runs, and a record of every run and model call
> - uploads of plain text, Markdown, Word and PDF files as source documents, with their origin recorded
> - Phase 7 tasks (clarify the brief, draft and review the requirements) that agent runs move through the workflow
> - requirement items with server-assigned IDs, labels, sources, derived statuses and rule-based quality checks, rendered as the requirements baseline document
> - a review loop: a reviewer's comments drive the redraft, which must answer each one
> - an approved baseline under change control: changes only through a change request approved by an owner and a customer approver (different people, not the raiser), applied by the agent and limited in code to the items it lists
> - a requirements traceability matrix (objectives, requirements, user stories, acceptance criteria, sources) with gap checks and CSV export
> - requirements reports (executive summary; detailed BRD and traceability) built only from records, versioned, with provenance; customers see the summary only
> - incident records opened automatically from failed agent runs, resolved with a root-cause analysis and closed by a different person
> - the Solution Architect agent: compares solution options (scored by the agent, totalled by Agentra) for people to choose, then drafts the solution design with stable IDs, unverified capabilities flagged, and every confirmed requirement covered or excepted; Phase 8 cannot complete otherwise, and a design goes stale when the approved requirements change
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
