# ADR 0002 — PostgreSQL from day one

- **Status:** Accepted (2026-11-02)
- **Supersedes:** spec direction of SQLite for the prototype.

## Decision
Use PostgreSQL (16+) with pgvector in every environment, installed natively on Windows for development (no Docker). One database covers operational data, workflow state, the job queue (`FOR UPDATE SKIP LOCKED`), the transactional outbox and the append-only, hash-chained audit trail. Artifact content lives in content-addressed storage (local folder → Azure Blob Storage); metadata in PostgreSQL.

## Consequences
- No Redis, Celery or separate vector database in the MVP.
- Row-level security is available for tenant isolation.
- Tests run against a real PostgreSQL test database.
