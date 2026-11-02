# Runs the FastAPI application locally on http://127.0.0.1:8000 with auto-reload.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_api.ps1 [-Port 8000] [-NoReload]
param(
    [int]$Port = 8000,
    [switch]$NoReload
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

$uvicornArgs = @('run', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', "$Port")
if (-not $NoReload) { $uvicornArgs += '--reload' }
uv @uvicornArgs
