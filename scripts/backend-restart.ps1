param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$Port = 8181,
    [switch]$Build,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "=== JARVIS Backend Restart ===" -ForegroundColor Cyan

$stopScript = Join-Path $RepoRoot "scripts\backend-stop.ps1"
$startScript = Join-Path $RepoRoot "scripts\backend-start.ps1"

if (-not (Test-Path $stopScript)) {
    Write-Host "[ERROR] backend-stop.ps1 nicht gefunden: $stopScript" -ForegroundColor Red
    exit 2
}

if (-not (Test-Path $startScript)) {
    Write-Host "[ERROR] backend-start.ps1 nicht gefunden: $startScript" -ForegroundColor Red
    exit 2
}

& $stopScript -RepoRoot $RepoRoot -Force:$Force
$stopExit = $LASTEXITCODE

if ($stopExit -eq 2) {
    exit 2
}

Start-Sleep -Seconds 2

& $startScript -RepoRoot $RepoRoot -Port $Port -Build:$Build
exit $LASTEXITCODE
