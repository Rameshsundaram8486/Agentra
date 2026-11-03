# Starts the agent worker: picks up queued agent runs (e.g. "Ask the Business Analyst agent") and runs them.
# Run it in its own terminal next to scripts\run_api.ps1. Ctrl+C stops it.
# Model calls need ANTHROPIC_API_KEY in .env; without it, runs fail with provider_not_configured.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run python -m app.workers.workflow_worker @args
