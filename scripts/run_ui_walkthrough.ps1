# Browser walkthrough of the Control Center against the TEST database (never the development one).
# Seeds three throwaway users, starts the API on port 8010, drives headless Edge (or Chrome) through
# sign-in, projects, team, documents, versions, diff, approval, decisions, phase tasks, a Word upload and asking the Business Analyst agent
# (the run stays queued: no worker and no model call), then stops the API.
# Screenshots and logs go to var\ui-walkthrough (gitignored). Exit code 0 means every step passed with no JS errors.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_ui_walkthrough.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$out = Join-Path $root 'var\ui-walkthrough'
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force $out | Out-Null

$browser = @(
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Google\Chrome\Application\chrome.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'Microsoft Edge or Google Chrome is required' }

$testUrl = (Get-Content (Join-Path $root '.env') | Where-Object { $_ -like 'TEST_DATABASE_URL=*' }) -replace '^TEST_DATABASE_URL=', ''
if (-not $testUrl) { throw 'TEST_DATABASE_URL is not set in .env' }

$env:DATABASE_URL = $testUrl
$env:AGENTRA_ENV = 'test'
$env:ARTIFACT_STORE_PATH = Join-Path $out 'store'
$env:PYTHONPATH = $root
$server = $null
try {
    uv run alembic upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'migrating the test database failed' }
    uv run python tests\e2e\seed_ui_users.py (Join-Path $out 'seed.json') | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'seeding walkthrough users failed' }

    $server = Start-Process uv -ArgumentList 'run', 'uvicorn', 'app.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8010' `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $out 'server.log') -RedirectStandardError (Join-Path $out 'server.err')
    $up = $false
    for ($i = 0; $i -lt 40 -and -not $up; $i++) {
        Start-Sleep -Milliseconds 500
        try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health -TimeoutSec 2 | Out-Null; $up = $true } catch {}
    }
    if (-not $up) { throw 'the API did not start; see var\ui-walkthrough\server.err' }

    node tests\e2e\ui_walkthrough.mjs http://127.0.0.1:8010 (Join-Path $out 'seed.json') (Join-Path $out 'screens') $browser
    $result = $LASTEXITCODE
} finally {
    if ($server) { taskkill /PID $server.Id /T /F | Out-Null }
    Remove-Item Env:DATABASE_URL, Env:AGENTRA_ENV, Env:ARTIFACT_STORE_PATH, Env:PYTHONPATH -ErrorAction SilentlyContinue
}
Write-Host "Screenshots: $out\screens"
exit $result
