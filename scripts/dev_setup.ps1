# One-time local setup: virtual environment, dependencies, database schema.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev_setup.ps1
# Prerequisites: uv, PostgreSQL running, .env filled in (scripts\create_db.ps1 writes the database URLs).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required. Install it with: winget install astral-sh.uv'
}

Write-Host '== Installing dependencies (uv sync)'
uv sync
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }

if (-not (Test-Path (Join-Path $root '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
    Write-Host 'Created .env from .env.example. Run scripts\create_db.ps1, then run this script again.'
    exit 0
}

Write-Host '== Applying database migrations to the development database'
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade failed; check DATABASE_URL in .env' }

Write-Host '== Done. Start the API with scripts\run_api.ps1 and run tests with: uv run pytest'
