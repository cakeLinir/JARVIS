param(
    [string]$RepoRoot = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$script:Errors = 0
$script:Warnings = 0

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-InfoStatus([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warn([string]$Message) {
    $script:Warnings += 1
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorStatus([string]$Message) {
    $script:Errors += 1
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-CommandExists([string]$Command) {
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
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
        Write-InfoStatus "$Role optional nicht vorhanden: $RelativePath"
    }
}

function Test-GitTracked([string]$RelativePath) {
    if (-not (Test-CommandExists "git")) {
        Write-Warn "git ist nicht im PATH. Secret-Tracking-Prüfung übersprungen."
        return $false
    }

    try {
        $output = git -C $RepoRoot ls-files -- $RelativePath 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }

        return [bool]($output | Where-Object { $_ -eq $RelativePath })
    }
    catch {
        Write-Warn "Git-Tracking-Prüfung fehlgeschlagen für ${RelativePath}: $($_.Exception.Message)"
        return $false
    }
}

function Test-SecretTracking([string]$RelativePath) {
    $path = Join-Path $RepoRoot $RelativePath
    $exists = Test-Path $path
    $tracked = Test-GitTracked $RelativePath

    if ($tracked) {
        Write-ErrorStatus "SICHERHEITSRISIKO: Secret-/Local-Datei ist von Git getrackt: $RelativePath"
        return
    }

    if ($exists) {
        Write-Ok "Secret-/Local-Datei existiert lokal, ist aber nicht getrackt: $RelativePath"
        return
    }

    Write-InfoStatus "Secret-/Local-Datei existiert nicht lokal und ist nicht getrackt: $RelativePath"
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

$secretPaths = @(
    "backend/.env",
    "backend/.env.local",
    "desktop-agent/config.local.json",
    ".env",
    ".env.local"
)

foreach ($relative in $secretPaths) {
    Test-SecretTracking $relative
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
