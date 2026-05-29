<#
.SYNOPSIS JARVIS VPS-Operationen – update-backend | update-project | check-layout
#>
param(
  [Parameter(Position = 0)] [ValidateSet("update-backend","update-project","check-layout")] [string]$Action,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$Branch = "main",
  [switch]$SkipGitPull,
  [switch]$SkipInstall,
  [switch]$SkipBackendBuild,
  [switch]$SkipDashboardBuild,
  [switch]$SkipCaddyReload,
  [switch]$AllowDirty
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$BackendDir = Join-Path $RepoRootResolved "backend"
$DashboardDir = Join-Path $RepoRootResolved "dashboard"

function Write-Info([string]$m) { Write-Host "[INFO] $m"  -ForegroundColor Cyan }
function Write-Ok([string]$m) { Write-Host "[OK] $m"    -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m"  -ForegroundColor Yellow }
function Write-Err([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red }
function Fail([string]$m) { Write-Err $m; exit 2 }
function Test-Cmd([string]$c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

function Invoke-GitPull {
  if ($SkipGitPull) { Write-Warn "Git Pull übersprungen."; return }
  Push-Location $RepoRootResolved
  try {
    $inside = & git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0 -or $inside.Trim() -ne "true") { Fail "Kein Git-Arbeitsbaum." }
    $branch = (& git branch --show-current).Trim()
    if ($branch -ne $Branch) { Write-Warn "Branch ist '$branch', erwartet '$Branch'." }
    $status = & git status --porcelain
    if ($status -and -not $AllowDirty) { Write-Host $status; Fail "Working tree nicht sauber. Nutze -AllowDirty." }
    & git fetch origin; if ($LASTEXITCODE -ne 0) { Fail "git fetch fehlgeschlagen." }
    & git pull --ff-only origin $Branch; if ($LASTEXITCODE -ne 0) { Fail "git pull fehlgeschlagen." }
    Write-Ok "Git Pull erfolgreich."
  } finally { Pop-Location }
}

function Update-Backend {
  Write-Host "=== JARVIS VPS Backend Update ===" -ForegroundColor Cyan
  if (-not (Test-Cmd "git")) { Fail "git nicht im PATH." }
  if (-not (Test-Cmd "npm")) { Fail "npm nicht im PATH." }
  if (-not (Test-Path (Join-Path $BackendDir "package.json"))) { Fail "backend\package.json fehlt." }
  Invoke-GitPull
  Push-Location $BackendDir
  try {
    if (-not (Test-Path ".env")) { Write-Warn "backend\.env fehlt." }
    if (-not $SkipInstall) { & npm install; if ($LASTEXITCODE -ne 0) { Fail "npm install fehlgeschlagen." }; Write-Ok "npm install OK." }
    if (-not $SkipBackendBuild) { & npm run build; if ($LASTEXITCODE -ne 0) { Fail "npm run build fehlgeschlagen." }; Write-Ok "Backend Build OK." }
  } finally { Pop-Location }
  Write-Ok "Backend Update abgeschlossen. Backend manuell neustarten: .\scripts\04_backend.ps1 -Action restart"
}

function Update-Project {
  Write-Host "=== JARVIS VPS Projekt-Update ===" -ForegroundColor Cyan
  if (-not (Test-Cmd "git")) { Fail "git nicht im PATH." }
  if (-not (Test-Cmd "npm")) { Fail "npm nicht im PATH." }
  if (-not (Test-Path (Join-Path $BackendDir   "package.json"))) { Fail "backend\package.json fehlt." }
  if (-not (Test-Path (Join-Path $DashboardDir "package.json"))) { Fail "dashboard\package.json fehlt. Sparse-Checkout ausführen." }
  Invoke-GitPull
  if (-not $SkipInstall) {
    foreach ($dir in @($BackendDir, $DashboardDir)) {
      Push-Location $dir
      try { & npm install; if ($LASTEXITCODE -ne 0) { Fail "npm install fehlgeschlagen in $dir." } }
    finally { Pop-Location }
  }
  Write-Ok "npm install (Backend + Dashboard) OK."
}
if (-not $SkipBackendBuild) {
  Push-Location $BackendDir; try { & npm run build; if ($LASTEXITCODE -ne 0) { Fail "Backend Build fehlgeschlagen." } } finally { Pop-Location }
  Write-Ok "Backend Build OK."
}
if (-not $SkipDashboardBuild) {
  Push-Location $DashboardDir; try { & npm run build; if ($LASTEXITCODE -ne 0) { Fail "Dashboard Build fehlgeschlagen." } } finally { Pop-Location }
  Write-Ok "Dashboard Build OK."
}
if (-not $SkipCaddyReload) {
  $caddyScript = Join-Path $RepoRootResolved "scripts\05_caddy.ps1"
  if (Test-Path $caddyScript) {
    & $caddyScript -Action install -Reload -RepoRoot $RepoRootResolved
    if ($LASTEXITCODE -ne 0) { Fail "Caddy Reload fehlgeschlagen." }
    Write-Ok "Caddy Reload OK."
  } else { Write-Warn "caddy.ps1 nicht gefunden. Caddy Reload übersprungen." }
}
Write-Ok "Projektupdate abgeschlossen."
}

function Check-Layout {
  Write-Host "=== JARVIS VPS Layout Check ===" -ForegroundColor Cyan
  $script:clErrors = 0; $script:clWarnings = 0
  function Ok([string]$m) { Write-Host "[OK] $m" -ForegroundColor Green }
  function Err([string]$m) { $script:clErrors++; Write-Host "[ERROR] $m" -ForegroundColor Red }
  function Wrn([string]$m) { $script:clWarnings++; Write-Host "[WARN] $m"  -ForegroundColor Yellow}
  function ChkPath([string]$rel, [string]$role, [bool]$req=$true) {
    if (Test-Path (Join-Path $RepoRootResolved $rel)) { Ok "$role vorhanden: $rel" }
  elseif ($req) { Err "$role fehlt: $rel" } else { Write-Host "[INFO] Optional fehlt: $rel" }
}
ChkPath "backend"               "Backend-Ordner"
ChkPath "backend\package.json"  "Backend package.json"
ChkPath "backend\src\server.ts" "Backend Server"
ChkPath "backend\.env"         "Backend .env"
ChkPath "scripts"              "Scripts-Ordner"
ChkPath "docs"                 "Docs-Ordner"
ChkPath "desktop-agent"        "Desktop-Agent" $false

# Secret-Tracking prüfen
Write-Host "--- Secret Tracking ---" -ForegroundColor Cyan
foreach ($rel in @("backend/.env","desktop-agent/config.local.json",".env")) {
  $tracked = try { & git -C $RepoRootResolved ls-files -- $rel 2>$null } catch { "" }
  if ($tracked -and $tracked.Trim()) { Err "SICHERHEITSRISIKO: Secret-Datei ist getrackt: $rel" }
elseif (Test-Path (Join-Path $RepoRootResolved $rel)) { Ok "$rel existiert lokal, nicht getrackt." }
else { Write-Host "[INFO] $rel nicht vorhanden, nicht getrackt." }
}

Write-Host "Errors: $script:clErrors  Warnings: $script:clWarnings" -ForegroundColor Cyan
if ($script:clErrors -gt 0) { exit 2 }
if ($script:clWarnings -gt 0) { exit 1 }
}

if (-not $Action) { Write-Host "Nutzung: vps.ps1 -Action <update-backend|update-project|check-layout>" -ForegroundColor Cyan; exit 0 }
switch ($Action) {
  "update-backend"  { Update-Backend }
  "update-project"  { Update-Project }
  "check-layout"    { Check-Layout }
}
