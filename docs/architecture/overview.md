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
| `workflow` | phase runs, tasks, state transitions; lifecycles from `config/workflows/` | audit, identity |
| `projects` | projects | audit, identity, workflow |

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
