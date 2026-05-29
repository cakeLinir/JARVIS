<#
.SYNOPSIS JARVIS Caddy – install | health
#>
param(
  [Parameter(Position = 0)] [ValidateSet("install","health")] [string]$Action,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [switch]$Reload,
  [string]$PublicUrl = "https://jarvis.hundekuchenlive.de",
  [string]$LocalUrl = "http://127.0.0.1:8181/api/health",
  [int] $TimeoutSec = 5
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path

function Write-Ok([string]$m) { Write-Host "[OK] $m"    -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m"  -ForegroundColor Yellow }
function Fail([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 2 }

function Install-CaddyConfig {
  $caddyFile = Join-Path $RepoRootResolved "deploy\caddy\Caddyfile"
  if (-not (Test-Path $caddyFile)) { Fail "Caddyfile nicht gefunden: $caddyFile" }
  if (-not (Get-Command "caddy" -ErrorAction SilentlyContinue)) { Fail "caddy nicht im PATH." }

  Write-Host "[INFO] Caddy Konfiguration wird validiert..." -ForegroundColor Cyan
  & caddy fmt --overwrite $caddyFile
  & caddy validate --config $caddyFile
  if ($LASTEXITCODE -ne 0) { Fail "Caddy Validierung fehlgeschlagen." }
  Write-Ok "Caddyfile validiert."

  $caddyDir = "C:\ProgramData\Caddy"
  if (-not (Test-Path $caddyDir)) { New-Item -ItemType Directory -Path $caddyDir -Force | Out-Null }
  Copy-Item -LiteralPath $caddyFile -Destination (Join-Path $caddyDir "Caddyfile") -Force
  Write-Ok "Caddyfile nach $caddyDir kopiert."

  if ($Reload) {
    & caddy reload --config (Join-Path $caddyDir "Caddyfile")
    if ($LASTEXITCODE -ne 0) { Fail "Caddy Reload fehlgeschlagen." }
    Write-Ok "Caddy Reload erfolgreich."
  }
}

function Test-CaddyHealth {
  Write-Host "=== JARVIS Caddy Health ===" -ForegroundColor Cyan
  foreach ($url in @($LocalUrl, "$($PublicUrl.TrimEnd('/'))/api/health")) {
    try {
      $r = Invoke-RestMethod $url -TimeoutSec $TimeoutSec
      if ($r.status -eq "ok" -or $r.ok) { Write-Ok "Health OK: $url" }
    else { Write-Warn "Health antwortet, aber nicht ok: $url" }
  } catch { Write-Warn "Nicht erreichbar: $url | $($_.Exception.Message)" }
}
}

if (-not $Action) { Write-Host "Nutzung: caddy.ps1 -Action <install|health>" -ForegroundColor Cyan; exit 0 }
switch ($Action) {
  "install" { Install-CaddyConfig }
  "health"  { Test-CaddyHealth }
}
