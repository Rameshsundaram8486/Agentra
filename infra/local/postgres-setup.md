# PostgreSQL setup (local, Windows)

Native PostgreSQL for development, no Docker (ADR 0002).

1. Install PostgreSQL 16+ from the EDB Windows installer. The service runs as `postgresql-x64-<version>` on port 5432.
2. Add `C:\Program Files\PostgreSQL\<version>\bin` to your user PATH, so `psql` works in new terminals.
3. Run `scripts\create_db.ps1`. It creates the `agentra` role and the `agentra_dev` and `agentra_test` databases, and writes `DATABASE_URL` and `TEST_DATABASE_URL` to `.env`.

pgvector is not installed yet. It will be added when the knowledge module needs it (after the MVP phases), together with a migration that runs `CREATE EXTENSION vector`.
