# Architecture overview

Agentra is a modular monolith: one FastAPI process plus background workers, on one PostgreSQL database. For the reasoning behind these choices, see `docs/adr/`.

## Request path

```
Browser (web/control-center, plain HTML/JS)
  -> FastAPI router (app/api/routers)        HTTP only: parse, call one service, commit
  -> dependencies (app/api/dependencies.py)  one UnitOfWork per request, session cookie -> Actor
  -> module services (app/modules/*/service.py)  business rules, authorisation, audit
  -> PostgreSQL
```

- **Routers** hold no business logic. They call a service and then `uow.commit()`. Anything not committed is rolled back.
- **`app/composition.py`** wires the services for one unit of work. The API, CLI, workers and tests all use it.
- **Domain errors** (`app/modules/errors.py`) map to HTTP status codes in `app/api/errors.py`: 401, 403, 404, 409 or 422.

## Modules built so far

| Module | Owns | Depends on |
|---|---|---|
| `audit` | `audit_events` | nothing |
| `identity` | users, sessions, memberships; permission checks (`config/policies/permissions.yaml`) | audit |
| `artifacts` | artifacts, versions; content in the content-addressed store (`app/infrastructure/storage`) | audit, identity |
| `decisions` | approvals, decision requests and outcomes; rules from `config/policies/approval_matrix.yaml` | audit, identity, artifacts |
| `workflow` | phase runs, tasks, state transitions; lifecycles from `config/workflows/` | audit, identity, decisions (approval gate) |
| `projects` | projects | audit, identity, workflow |
| `executions` | agent runs (linked to workflow tasks, with their inputs), model calls (the spend ledger) | audit, identity, artifacts, workflow, decisions |
| `requirements` | requirement items, versions and the item ID registry; quality checks; BRD rendering | audit, identity, artifacts, decisions, projects |

## Approvals and decisions

- **Only people approve or decide.** Agent and system accounts are refused in code, and a policy file that lists `agent` as an approver or decider fails startup.
- **An approval is tied to one exact version.** It names the version id and the SHA-256 of the content the reviewer saw. Both must match, the version must still be current, and the stored bytes are re-hashed before the approval is recorded.
- **Authors can't approve their own work.** With `independent_review: true`, nobody who authored any version of an artifact can approve it.
- **Phase completion needs approvals.** Each phase file lists `exit.required_approvals`. Completing the phase needs every artifact of those types approved at its current version. Adding a new version voids the earlier approval.
- **Recommendations are preserved.** A decision request stores the recommendation exactly as raised. Each human response (accept, choose another option, something else, modify, reject, defer) is a separate numbered outcome.

## Agent runs

```
Person clicks "Ask the Business Analyst agent"
  -> executions.request_run        permission agent.run; phase state and agent membership checked;
                                   run + job created in one transaction (same version twice -> same run)
Worker (app/workers/workflow_worker.py) claims the job
  -> harness/runner.py             preconditions checked again
  -> agent task prepare            reads the brief through the agent's own permissions;
                                   G1: secrets redacted, injection flagged, brief wrapped as data
  -> model_gateway.call            reserves the worst-case cost against the monthly cap (committed),
                                   calls Claude, settles real usage, cost and the model that answered
  -> guardrails G4                 schema; every source quote must appear in the brief;
                                   no approval/decision/test/deploy claims; no secrets
  -> agent task apply              decision requests raised as the agent account, linked to the brief version
  -> run finished                  succeeded / failed / blocked, with findings and reason; audited
```

- **Nothing a model writes is saved unless every output check passed.** A blocked output is kept only as a redacted excerpt on the run, for diagnosis.
- **Agents propose; people decide.** The agent's questions arrive as open decision requests. Agents cannot record outcomes or approvals.
- **Retries:** only transient provider errors are retried, by the job queue up to the task's `max_attempts`. Refusals, guardrail failures and the budget are final. Asking again after a failed run starts a new run.
- **Model routing and spend:** `config/models.yaml` (model, effort, token limit and timeout per agent, prices, monthly cap). Agent definitions, prompts and output schemas: `config/agents/<key>/`. A prompt's version is its file name plus a content hash, recorded on every call.

## Phase 7 flow

| Step | Who | Workflow task |
|---|---|---|
| Add the brief (typed or uploaded) and any source documents | Project manager | |
| Ask the agent about the brief | Owner or project manager; the agent runs | Clarify: in progress, then waiting for input |
| Answer the questions in the decision inbox; close the Clarify task | People | Clarify: completed |
| Ask the agent to draft the requirements | Owner or project manager; the agent runs | Draft: in progress, then waiting for input (open questions) or waiting for review |
| Answer its open questions and ask again; the IDs of kept items stay the same | People, then the agent | Draft: back to in progress |
| Request changes on the document with a comment, then ask for a redraft | Reviewer, then owner or project manager | Draft: changes requested (recorded by Agentra), in progress |
| Approve the requirements baseline version, then complete the task | Reviewer or owner (never its author) | Draft: completed, only once the current version is approved |
| Raise a change request against the approved baseline | Owner or project manager | (no task) |
| Approve it: one owner and one customer approver, different people, not the raiser | People | (no task) |
| Ask the agent to apply it; approve the new version | Owner or project manager; then a reviewer | (no task; works after the phase completes too) |

- **Inputs are fixed when a run is asked for:** the chosen brief version, the current source documents and the state of the decisions it reads. The same inputs never produce a second run; a changed answer or document does.
- **Statuses are derived in code:** confirmed only for a fact backed by a quoted document or an answered decision; assumptions and suggestions are proposed; questions are open. The model never sets a status or an ID.
- **An approved baseline is under change control** (`baselines` in `approval_matrix.yaml`). Nobody can add a version directly. An approved change request can, and only through the requirements service, which checks in code that every item it does not list comes back unchanged, that only listed items are removed, and that new items appear only if allowed. The agent task runs the same check first, so a violating answer is never saved.
- **Review comments are inputs.** A redraft reads every comment requesting changes on the current version and must answer each one; the answers are stored with the version and shown in the document.
- **The Clarify task cannot be closed while a question it raised is still open** (answer or defer it).
- Uploaded files are parsed on the host with size, page and decompression limits; the extracted text is what agents read and quote, and the original file is kept by its hash.

## Authorisation

- Permissions come from project roles (membership) plus platform-admin rights, as defined in `permissions.yaml`.
- Workflow transitions are authorised separately: each transition in a lifecycle YAML lists the roles that may request it.
- Someone who cannot see a project gets 404, never 403, so they cannot learn that it exists.
- Agents are service accounts. They hold the `agent` role, cannot sign in, and are never allowed to complete a review. An agent may move only workflow tasks assigned to it.

## Configuration as data

`config/workflows/`, `config/policies/`, `config/agents/` and `config/models.yaml` are loaded and validated when the app starts, including cross-references (an agent task's document types, phase and phase states must exist). An invalid file stops startup rather than failing later at runtime.

## Security headers

- Pages under `/app/` get a strict Content-Security-Policy (`'self'` only, no inline scripts).
- Every response gets `nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.
- API responses also get `Cache-Control: no-store`.
- Session cookies are HttpOnly and SameSite=Strict, plus Secure when `AGENTRA_ENV=production`.
