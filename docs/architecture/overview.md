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

## Approvals and decisions

- **Only people approve or decide.** Agent and system accounts are refused in code, and a policy file that lists `agent` as an approver or decider fails startup.
- **An approval is tied to one exact version.** It names the version id and the SHA-256 of the content the reviewer saw. Both must match, the version must still be current, and the stored bytes are re-hashed before the approval is recorded.
- **Authors can't approve their own work.** With `independent_review: true`, nobody who authored any version of an artifact can approve it.
- **Phase completion needs approvals.** Each phase file lists `exit.required_approvals`. Completing the phase needs every artifact of those types approved at its current version. Adding a new version voids the earlier approval.
- **Recommendations are preserved.** A decision request stores the recommendation exactly as raised. Each human response (accept, choose another option, something else, modify, reject, defer) is a separate numbered outcome.

## Authorisation

- Permissions come from project roles (membership) plus platform-admin rights, as defined in `permissions.yaml`.
- Workflow transitions are authorised separately: each transition in a lifecycle YAML lists the roles that may request it.
- Someone who cannot see a project gets 404, never 403, so they cannot learn that it exists.
- Agents are service accounts. They hold the `agent` role, cannot sign in, and are never allowed to complete a review.

## Configuration as data

`config/workflows/` and `config/policies/` are loaded and validated when the app starts. An invalid file stops startup rather than failing later at runtime.

## Security headers

- Pages under `/app/` get a strict Content-Security-Policy (`'self'` only, no inline scripts).
- Every response gets `nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.
- API responses also get `Cache-Control: no-store`.
- Session cookies are HttpOnly and SameSite=Strict, plus Secure when `AGENTRA_ENV=production`.
