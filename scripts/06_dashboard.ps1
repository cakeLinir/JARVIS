<#
.SYNOPSIS JARVIS Dashboard – build | deploy | check
#>
param(
  [Parameter(Position = 0)] [ValidateSet("build","deploy","check")] [string]$Action,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [switch]$ReloadCaddy
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$DashboardDir = Join-Path $RepoRootResolved "dashboard"

function Write-Info([string]$m) { Write-Host "[INFO] $m"  -ForegroundColor Cyan }
function Write-Ok([string]$m) { Write-Host "[OK] $m"    -ForegroundColor Green }
function Fail([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 2 }

function Build-Dashboard {
  Write-Info "Baue Dashboard..."
  if (-not (Test-Path (Join-Path $DashboardDir "package.json"))) {
    Fail "dashboard\package.json fehlt. Sparse-Checkout prüfen: .\scripts\config.ps1 -Action vps-sparse"
  }
  Push-Location $DashboardDir
  try { & npm run build; if ($LASTEXITCODE -ne 0) { Fail "npm run build fehlgeschlagen." } }
finally { Pop-Location }
Write-Ok "Dashboard Build erfolgreich."
}

function Deploy-Dashboard {
  Build-Dashboard
  if ($ReloadCaddy) {
    $caddyScript = Join-Path $RepoRootResolved "scripts\05_caddy.ps1"
    if (-not (Test-Path $caddyScript)) { Fail "05_caddy.ps1 nicht gefunden." }
    Write-Info "Caddy Reload..."
    & $caddyScript -Action install -Reload -RepoRoot $RepoRootResolved
    if ($LASTEXITCODE -ne 0) { Fail "Caddy Reload fehlgeschlagen." }
    Write-Ok "Caddy Reload erfolgreich."
  } else {
    Write-Info "Caddy Reload übersprungen. Nutze -ReloadCaddy."
  }
}

function Check-Dashboard {
  Write-Host "=== JARVIS Dashboard Source Check ===" -ForegroundColor Cyan
  $pkgJson = Join-Path $DashboardDir "package.json"
  $distIdx = Join-Path $DashboardDir "dist\index.html"
  if (Test-Path $pkgJson) { Write-Ok "dashboard\package.json vorhanden." }
else { Fail "dashboard\package.json fehlt." }
if (Test-Path $distIdx) { Write-Ok "dashboard\dist\index.html vorhanden." }
else { Write-Host "[WARN] dist\index.html fehlt. Führe .\scripts\dashboard.ps1 -Action build aus." -ForegroundColor Yellow; exit 1 }
}

if (-not $Action) { Write-Host "Nutzung: dashboard.ps1 -Action <build|deploy|check>" -ForegroundColor Cyan; exit 0 }
switch ($Action) {
  "build"  { Build-Dashboard }
  "deploy" { Deploy-Dashboard }
  "check"  { Check-Dashboard }
}
