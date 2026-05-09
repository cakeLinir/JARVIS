param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$Branch = "main",
    [switch]$SkipInstall,
    [switch]$SkipBackendBuild,
    [switch]$SkipDashboardBuild,
    [switch]$SkipCaddyReload,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

function Test-CommandExists([string]$Command) {
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path

Push-Location $repoRootResolved
try {
    if (-not (Test-CommandExists "git")) { Fail "git ist nicht im PATH." }
    if (-not (Test-CommandExists "npm")) { Fail "npm ist nicht im PATH." }

    $insideWorkTree = (& git rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -ne 0 -or $insideWorkTree.Trim() -ne "true") {
        Fail "RepoRoot ist kein Git-Arbeitsbaum."
    }

    $currentBranch = (& git branch --show-current).Trim()
    if ($currentBranch -ne $Branch) {
        Write-Warn "Aktueller Branch ist '$currentBranch', erwartet '$Branch'."
    }

    $status = (& git status --porcelain)
    if ($status -and -not $AllowDirty) {
        Write-Host $status
        Fail "Working tree ist nicht sauber. Committe/stashe Änderungen oder nutze bewusst -AllowDirty."
    }

    Write-Info "Git fetch/pull..."
    & git fetch origin
    if ($LASTEXITCODE -ne 0) { Fail "git fetch fehlgeschlagen." }

    & git pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) { Fail "git pull --ff-only fehlgeschlagen." }

    Write-Ok "Git Pull erfolgreich."
}
finally {
    Pop-Location
}

$backendDir = Join-Path $repoRootResolved "backend"
$dashboardDir = Join-Path $repoRootResolved "dashboard"

if (-not (Test-Path (Join-Path $backendDir "package.json"))) {
    Fail "backend\package.json fehlt."
}

if (-not (Test-Path (Join-Path $dashboardDir "package.json"))) {
    Fail "dashboard\package.json fehlt. Führe .\scripts\configure-vps-sparse-checkout.ps1 -ApplyPull aus oder prüfe, ob Patch 018 gepusht wurde."
}

if (-not $SkipInstall) {
    Write-Info "Installiere Backend Dependencies..."
    Push-Location $backendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) { Fail "npm install im Backend fehlgeschlagen." }
    }
    finally { Pop-Location }

    Write-Info "Installiere Dashboard Dependencies..."
    Push-Location $dashboardDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) { Fail "npm install im Dashboard fehlgeschlagen." }
    }
    finally { Pop-Location }
}

if (-not $SkipBackendBuild) {
    Write-Info "Baue Backend..."
    Push-Location $backendDir
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { Fail "Backend Build fehlgeschlagen." }
    }
    finally { Pop-Location }
    Write-Ok "Backend Build erfolgreich."
}

if (-not $SkipDashboardBuild) {
    Write-Info "Baue Dashboard..."
    Push-Location $dashboardDir
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { Fail "Dashboard Build fehlgeschlagen." }
    }
    finally { Pop-Location }
    Write-Ok "Dashboard Build erfolgreich."
}

if (-not $SkipCaddyReload) {
    $caddyScript = Join-Path $repoRootResolved "scripts\caddy-install-jarvis-config.ps1"
    if (Test-Path $caddyScript) {
        Write-Info "Aktualisiere Caddy-Konfiguration..."
        & $caddyScript -RepoRoot $repoRootResolved -Reload
        if ($LASTEXITCODE -ne 0) { Fail "Caddy Reload fehlgeschlagen." }
        Write-Ok "Caddy Reload erfolgreich."
    }
    else {
        Write-Warn "caddy-install-jarvis-config.ps1 nicht gefunden. Caddy Reload übersprungen."
    }
}

Write-Ok "VPS Projektupdate abgeschlossen."
