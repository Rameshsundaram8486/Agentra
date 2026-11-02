# Creates the local PostgreSQL role (agentra) and databases (agentra_dev, agentra_test),
# then writes DATABASE_URL and TEST_DATABASE_URL into .env. Safe to re-run: existing objects are left as they are.
# The postgres superuser password is taken from $env:PGPASSWORD or prompted for; it is never stored.
# The agentra role gets a random password that is written only to .env (gitignored).
# pgvector is added later, when the knowledge module needs it.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\create_db.ps1
param(
    [string]$PgBin = 'C:\Program Files\PostgreSQL\18\bin',
    [string]$PgHost = 'localhost',
    [int]$Port = 5432
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'
$psql = Join-Path $PgBin 'psql.exe'
if (-not (Test-Path $psql)) { throw "psql.exe not found in $PgBin (pass -PgBin)" }

function Invoke-Psql([string]$Sql) {
    $output = $Sql | & $psql -h $PgHost -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -qtA
    if ($LASTEXITCODE -ne 0) { throw 'psql failed' }
    return "$output".Trim()
}

function Set-EnvValue([string[]]$Lines, [string]$Key, [string]$Value) {
    $found = $false
    $result = foreach ($line in $Lines) {
        if ($line -match "^$Key=") { $found = $true; "$Key=$Value" } else { $line }
    }
    if (-not $found) { $result = @($result) + "$Key=$Value" }
    return ,@($result)
}

$suppliedPassword = [bool]$env:PGPASSWORD
if (-not $suppliedPassword) {
    $secure = Read-Host 'postgres superuser password' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

$password = $null
try {
    if ((Invoke-Psql "SELECT count(*) FROM pg_roles WHERE rolname = 'agentra';") -eq '0') {
        $alphabet = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
        $bytes = New-Object byte[] 32
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $password = -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })
        Invoke-Psql "CREATE ROLE agentra LOGIN PASSWORD '$password' NOSUPERUSER NOCREATEDB NOCREATEROLE;" | Out-Null
        Write-Host 'Created role agentra'
    } else {
        Write-Host 'Role agentra already exists (password unchanged)'
    }

    foreach ($db in 'agentra_dev', 'agentra_test') {
        if ((Invoke-Psql "SELECT count(*) FROM pg_database WHERE datname = '$db';") -eq '0') {
            Invoke-Psql "CREATE DATABASE $db OWNER agentra ENCODING 'UTF8' TEMPLATE template0;" | Out-Null
            Invoke-Psql "REVOKE CONNECT ON DATABASE $db FROM PUBLIC;" | Out-Null
            Write-Host "Created database $db"
        } else {
            Write-Host "Database $db already exists"
        }
    }
} finally {
    if (-not $suppliedPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
}

if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $root '.env.example') $envFile }
$lines = @(Get-Content $envFile)

if ($password) {
    $base = "postgresql+psycopg://agentra:$password@${PgHost}:$Port"
    $lines = Set-EnvValue $lines 'DATABASE_URL' "$base/agentra_dev"
    $lines = Set-EnvValue $lines 'TEST_DATABASE_URL' "$base/agentra_test"
    [IO.File]::WriteAllText($envFile, (($lines -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Wrote DATABASE_URL and TEST_DATABASE_URL to .env'
} elseif (-not ($lines | Where-Object { $_ -match '^DATABASE_URL=.+' })) {
    Write-Warning 'Role agentra already existed, so its password is unknown here. Set DATABASE_URL and TEST_DATABASE_URL in .env by hand, or reset the role password.'
} else {
    Write-Host '.env already has DATABASE_URL; left unchanged'
}
