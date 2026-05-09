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

$forbiddenCommitted = @(
    "backend\.env.example.local",
    "desktop-agent\config.local.json",
    ".env",
    ".env.local"
)

foreach ($relative in $forbiddenCommitted) {
    $path = Join-Path $RepoRoot $relative
    if (Test-Path $path) {
        Write-Warn "Lokale/Secret-Datei existiert im Arbeitsbaum: $relative. Nicht committen."
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
