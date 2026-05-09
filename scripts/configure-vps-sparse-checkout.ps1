param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [switch]$ApplyPull
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

$repoRootResolved = (Resolve-Path $RepoRoot).Path

Push-Location $repoRootResolved
try {
    $insideWorkTree = (& git rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -ne 0 -or $insideWorkTree.Trim() -ne "true") {
        Fail "RepoRoot ist kein Git-Arbeitsbaum: $repoRootResolved"
    }

    $status = (& git status --porcelain)
    if ($status) {
        Write-Warn "Working tree ist nicht sauber. Sparse-Checkout wird trotzdem konfiguriert, aber Pull kann fehlschlagen."
        Write-Host $status
    }

    Write-Info "Aktiviere Sparse Checkout..."
    & git sparse-checkout init --cone
    if ($LASTEXITCODE -ne 0) { Fail "git sparse-checkout init fehlgeschlagen." }

    $paths = @(
        "backend",
        "dashboard",
        "deploy",
        "docs",
        "scripts",
        ".gitignore",
        "README.md",
        "LICENSE"
    )

    Write-Info "Setze produktive VPS-Pfade:"
    foreach ($path in $paths) {
        Write-Host "  $path"
    }

    & git sparse-checkout set @paths
    if ($LASTEXITCODE -ne 0) { Fail "git sparse-checkout set fehlgeschlagen." }

    Write-Ok "Sparse Checkout konfiguriert."

    if ($ApplyPull) {
        Write-Info "Hole aktuellen Stand vom Remote..."
        & git pull --ff-only
        if ($LASTEXITCODE -ne 0) { Fail "git pull --ff-only fehlgeschlagen." }
        Write-Ok "git pull erfolgreich."
    }

    Write-Host ""
    Write-Host "Prüfung:" -ForegroundColor Cyan
    Write-Host "  Test-Path .\dashboard\package.json"
    Write-Host "  Test-Path .\deploy\caddy\Caddyfile"
}
finally {
    Pop-Location
}
