param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$Branch = "main",
    [switch]$SkipGitPull,
    [switch]$SkipInstall,
    [switch]$SkipBuild,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

function Test-CommandExists([string]$Command) {
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

Write-Host "=== JARVIS VPS Backend Update ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Branch: $Branch"

if (-not (Test-Path $RepoRoot)) {
    Fail "RepoRoot existiert nicht: $RepoRoot"
}

$backendDir = Join-Path $RepoRoot "backend"
if (-not (Test-Path (Join-Path $backendDir "package.json"))) {
    Fail "backend\package.json nicht gefunden. Falscher RepoRoot?"
}

if (-not (Test-CommandExists "git")) {
    Fail "git ist nicht im PATH."
}

if (-not (Test-CommandExists "npm")) {
    Fail "npm ist nicht im PATH."
}

Push-Location $RepoRoot
try {
    $insideWorkTree = (& git rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -ne 0 -or $insideWorkTree.Trim() -ne "true") {
        Fail "RepoRoot ist kein Git-Arbeitsbaum."
    }

    $currentBranch = (& git branch --show-current).Trim()
    if ($currentBranch -ne $Branch) {
        Write-Warn "Aktueller Branch ist '$currentBranch', erwartet '$Branch'."
    }
    else {
        Write-Ok "Branch korrekt: $currentBranch"
    }

    $status = (& git status --porcelain)
    if ($status -and -not $AllowDirty) {
        Write-Host $status
        Fail "Working tree ist nicht sauber. Committe/stashe Änderungen oder nutze bewusst -AllowDirty."
    }

    if ($status -and $AllowDirty) {
        Write-Warn "Working tree ist dirty, -AllowDirty gesetzt. Fahre fort."
    }

    if ($SkipGitPull) {
        Write-Warn "Git Pull übersprungen."
    }
    else {
        Write-Info "Hole Änderungen vom Remote..."
        & git fetch origin
        if ($LASTEXITCODE -ne 0) {
            Fail "git fetch fehlgeschlagen."
        }

        & git pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) {
            Fail "git pull --ff-only fehlgeschlagen. Prüfe Branch/Remote/ lokale Änderungen."
        }

        Write-Ok "Git Pull erfolgreich."
    }
}
finally {
    Pop-Location
}

Push-Location $backendDir
try {
    if (-not (Test-Path ".env")) {
        Write-Warn "backend\.env fehlt. Backend kann ohne echte Secrets nicht produktiv starten."
    }
    else {
        Write-Ok "backend\.env vorhanden."
    }

    if ($SkipInstall) {
        Write-Warn "npm install übersprungen."
    }
    else {
        Write-Info "npm install..."
        & npm install
        if ($LASTEXITCODE -ne 0) {
            Fail "npm install fehlgeschlagen."
        }
        Write-Ok "npm install erfolgreich."
    }

    if ($SkipBuild) {
        Write-Warn "npm run build übersprungen."
    }
    else {
        Write-Info "npm run build..."
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            Fail "npm run build fehlgeschlagen."
        }
        Write-Ok "npm run build erfolgreich."
    }
}
finally {
    Pop-Location
}

Write-Ok "VPS Backend Update abgeschlossen."
Write-Host "Backend danach manuell oder per Service neu starten." -ForegroundColor Cyan
exit 0
