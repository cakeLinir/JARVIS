param(
    [string]$RepoRoot = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$script:Errors = 0
$script:Warnings = 0

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    $script:Warnings += 1
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorStatus([string]$Message) {
    $script:Errors += 1
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-PathRole([string]$RelativePath, [string]$Role, [bool]$Required = $true) {
    $path = Join-Path $RepoRoot $RelativePath
    if (Test-Path $path) {
        Write-Ok "$Role vorhanden: $RelativePath"
        return
    }

    if ($Required) {
        Write-ErrorStatus "$Role fehlt: $RelativePath"
    }
    else {
        Write-Warn "$Role optional nicht vorhanden: $RelativePath"
    }
}

function Test-GitAvailable() {
    try {
        git -C $RepoRoot rev-parse --is-inside-work-tree *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-GitTracked([string]$RelativePath) {
    if (-not (Test-GitAvailable)) {
        return $false
    }

    git -C $RepoRoot ls-files --error-unmatch -- $RelativePath *> $null
    return $LASTEXITCODE -eq 0
}

Write-Host "=== JARVIS VPS Layout Check ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"

if (-not (Test-Path $RepoRoot)) {
    Write-ErrorStatus "RepoRoot existiert nicht: $RepoRoot"
    exit 2
}

Test-PathRole "backend" "Backend-Ordner" $true
Test-PathRole "backend\package.json" "Backend package.json" $true
Test-PathRole "backend\src\server.ts" "Backend Server" $true
Test-PathRole "backend\.env" "Backend .env" $true
Test-PathRole "scripts" "Scripts-Ordner" $true
Test-PathRole "scripts\preflight-vps.ps1" "VPS Preflight" $true
Test-PathRole "scripts\vps-update-backend.ps1" "VPS Update-Skript" $true
Test-PathRole "docs" "Docs-Ordner" $true
Test-PathRole "desktop-agent" "Desktop-Agent Quellcode" $false

Write-Host ""
Write-Host "--- Secret-/Local-Tracking Check ---" -ForegroundColor Cyan

$forbiddenTracked = @(
    "backend/.env",
    "backend/.env.local",
    "desktop-agent/config.local.json",
    ".env",
    ".env.local"
)

foreach ($relative in $forbiddenTracked) {
    $path = Join-Path $RepoRoot ($relative -replace "/", "\")
    if (Test-GitTracked $relative) {
        Write-ErrorStatus "Secret-/Local-Datei ist von Git getrackt: $relative"
        continue
    }

    if (Test-Path $path) {
        Write-Ok "Lokale Datei vorhanden, aber nicht getrackt: $relative"
    }
    else {
        Write-Ok "Nicht vorhanden/nicht getrackt: $relative"
    }
}

Write-Host ""
Write-Host "=== Ergebnis ===" -ForegroundColor Cyan
Write-Host "Errors: $script:Errors"
Write-Host "Warnings: $script:Warnings"

if ($script:Errors -gt 0) {
    exit 2
}

if ($script:Warnings -gt 0) {
    exit 1
}

exit 0
