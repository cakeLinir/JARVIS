<#
.SYNOPSIS JARVIS Preflight-Prüfung – local | vps
#>
param(
  [Parameter(Position = 0)] [ValidateSet("local","vps")] [string]$Target,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [int] $ExpectedPort = 8181,
  [switch]$SkipBackendBuild,
  [switch]$SkipAgentCompile,
  [switch]$CheckLocalApi,
  [string]$LocalApiUrl = "http://127.0.0.1:8765/health"
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$script:Errors = 0; $script:Warnings = 0

function Write-Ok([string]$m) { Write-Host "[OK] $m"   -ForegroundColor Green }
function Write-Warn([string]$m) { $script:Warnings++; Write-Host "[WARN] $m"   -ForegroundColor Yellow }
function Write-Err([string]$m) { $script:Errors++; Write-Host "[ERROR] $m"  -ForegroundColor Red }
function Write-Req([string]$m) { $script:Warnings++; Write-Host "[KONFIGURATION_ERFORDERLICH] $m" -ForegroundColor Yellow }
function Test-Cmd([string]$c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Req-Path([string]$rel, [bool]$required=$true) {
  $path = Join-Path $RepoRootResolved $rel
  if (Test-Path $path) { Write-Ok "Gefunden: $rel" }
elseif ($required) { Write-Err "Fehlt: $rel" }
else { Write-Host "[INFO] Optional fehlt: $rel" }
}
function Read-Env([string]$path) {
  $r = @{}
  if (-not (Test-Path $path)) { return $r }
  foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
    $t = $line.Trim(); if (-not $t -or $t.StartsWith("#")) { continue }
    $i = $t.IndexOf("="); if ($i -le 0) { continue }
    $r[$t.Substring(0,$i).Trim()] = $t.Substring($i+1).Trim()
  }
  return $r
}
function Check-Secret([hashtable]$env, [string]$key) {
  if (-not $env.ContainsKey($key)) { Write-Req "$key fehlt."; return }
  $v = [string]$env[$key]; $u = $v.ToUpperInvariant()
  if (-not $v -or $u.Contains("CHANGE_ME") -or $u.Contains("PLACEHOLDER")) { Write-Req "$key ist Platzhalter."; return }
  Write-Ok "$key gesetzt."
}
function Check-GitTracked([string]$rel) {
  if (-not (Test-Cmd "git")) { return $false }
  try {
    $tracked = & git -C $RepoRootResolved ls-files -- $rel 2>$null
    return [bool]($tracked | Where-Object { $_ -eq $rel })
  } catch { return $false }
}

# ── Local Preflight ───────────────────────────────────────────────────────────

function Invoke-LocalPreflight {
  Write-Host "=== JARVIS Local Preflight ===" -ForegroundColor Cyan
  Req-Path "README.md"
  Req-Path "backend\package.json"
  Req-Path "backend\src\server.ts"
  Req-Path "desktop-agent\src\main.py"
  Req-Path "desktop-agent\config.json"
  Req-Path "scripts\07_task.ps1" $false

  Write-Host "--- Tooling ---" -ForegroundColor Cyan
  if (Test-Cmd "node") { Write-Ok "Node: $(& node --version)" } else { Write-Err "Node.js fehlt." }
  if (Test-Cmd "npm") { Write-Ok "npm: $(& npm --version)"   } else { Write-Err "npm fehlt." }
  if (Test-Cmd "py") { Write-Ok "Python: $(& py -3 --version)" } else { Write-Err "py fehlt." }

  Write-Host "--- Backend Konfiguration ---" -ForegroundColor Cyan
  $envPath = Join-Path $RepoRootResolved "backend\.env"
  if (Test-Path $envPath) {
    $env = Read-Env $envPath
    Check-Secret $env "OPENAI_API_KEY"; Check-Secret $env "JARVIS_AGENT_TOKEN"
    Check-Secret $env "JARVIS_BOT_BRIDGE_TOKEN"; Check-Secret $env "JARVIS_DASHBOARD_TOKEN"
    if ($env["JARVIS_BACKEND_PORT"] -eq "8181") { Write-Ok "Port 8181." } else { Write-Warn "JARVIS_BACKEND_PORT ist nicht 8181." }
  } else { Write-Req "backend\.env fehlt." }

  Write-Host "--- Agent Konfiguration ---" -ForegroundColor Cyan
  $cfgPath = Join-Path $RepoRootResolved "desktop-agent\config.json"
  if (Test-Path $cfgPath) {
    try { $cfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8 -Raw | ConvertFrom-Json; Write-Ok "config.json ist gültiges JSON." } catch { Write-Err "config.json ungültig." }
  }
  $localCfg = Join-Path $RepoRootResolved "desktop-agent\config.local.json"
  if (Test-Path $localCfg) { Write-Ok "config.local.json vorhanden." } else { Write-Req "config.local.json fehlt." }

  Write-Host "--- Neue Agent-Module ---" -ForegroundColor Cyan
  foreach ($m in @("utils\date_resolver.py","shifts\shift_parser.py","shifts\shift_client.py","todo\todo_client.py","todo\reminder_engine.py")) {
    Req-Path "desktop-agent\src\$m" $false
  }

  Write-Host "--- Backend Build ---" -ForegroundColor Cyan
  if ($SkipBackendBuild) { Write-Warn "Backend Build übersprungen." }
elseif (Test-Path (Join-Path $RepoRootResolved "backend\package.json")) {
  Push-Location (Join-Path $RepoRootResolved "backend")
  try { & npm run build; if ($LASTEXITCODE -eq 0) { Write-Ok "Build OK." } else { Write-Err "Build fehlgeschlagen." } }
finally { Pop-Location }
}

Write-Host "--- Agent Python Compile ---" -ForegroundColor Cyan
if ($SkipAgentCompile) { Write-Warn "Compile übersprungen." }
elseif (Test-Cmd "py") {
  $pyFiles = Get-ChildItem -LiteralPath (Join-Path $RepoRootResolved "desktop-agent\src") -Recurse -Filter "*.py" |
    Where-Object { $_.FullName -notmatch "__pycache__" } | ForEach-Object { $_.FullName }
  & py -3 -m py_compile @pyFiles
  if ($LASTEXITCODE -eq 0) { Write-Ok "Python Compile OK." } else { Write-Err "Python Compile fehlgeschlagen." }
}
}

# ── VPS Preflight ─────────────────────────────────────────────────────────────

function Invoke-VpsPreflight {
  Write-Host "=== JARVIS VPS Preflight ===" -ForegroundColor Cyan
  Req-Path "backend\package.json"
  Req-Path "backend\src\server.ts"
  Req-Path "docs"

  Write-Host "--- Tooling ---" -ForegroundColor Cyan
  if (Test-Cmd "node") { Write-Ok "Node: $(& node --version)" } else { Write-Err "Node.js fehlt." }
  if (Test-Cmd "npm") { Write-Ok "npm: $(& npm --version)"   } else { Write-Err "npm fehlt." }

  Write-Host "--- Backend .env ---" -ForegroundColor Cyan
  $envPath = Join-Path $RepoRootResolved "backend\.env"
  if (Test-Path $envPath) {
    $env = Read-Env $envPath
    Check-Secret $env "OPENAI_API_KEY"; Check-Secret $env "JARVIS_AGENT_TOKEN"
    Check-Secret $env "JARVIS_BOT_BRIDGE_TOKEN"; Check-Secret $env "JARVIS_DASHBOARD_TOKEN"
    if ($env["JARVIS_BACKEND_PORT"] -eq "$ExpectedPort") { Write-Ok "Port $ExpectedPort." } else { Write-Warn "Port stimmt nicht." }
  } else { Write-Req "backend\.env fehlt." }

  Write-Host "--- Runtime-Dateien ---" -ForegroundColor Cyan
  $dataDir = Join-Path $RepoRootResolved "backend\.runtime\data"
  if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir -Force | Out-Null; Write-Ok "Runtime-Dir erstellt." }
else { Write-Ok "Runtime-Dir vorhanden." }
foreach ($f in @("todos.json","shifts.json","commands.json","audit-log.jsonl")) {
  $rel = "backend/.runtime/data/$f"
  if (Check-GitTracked $rel) { Write-Warn "$f ist von Git getrackt! Runtime-Dateien nicht committen." }
else { Write-Ok "$f ist nicht getrackt." }
}

Write-Host "--- Neue Domänen ---" -ForegroundColor Cyan
foreach ($f in @("routes\todo.routes.ts","routes\shift.routes.ts","routes\streaming.routes.ts",
"services\todo-store.ts","services\shift-store.ts","services\streaming-advice.service.ts",
"types\todo.types.ts","types\shift.types.ts")) {
  Req-Path "backend\src\$f" $false
}

Write-Host "--- Port ---" -ForegroundColor Cyan
try {
  $conn = Get-NetTCPConnection -LocalPort $ExpectedPort -ErrorAction SilentlyContinue
  if ($conn) { Write-Warn "Port $ExpectedPort belegt." } else { Write-Ok "Port $ExpectedPort frei." }
} catch {}

Write-Host "--- Backend Build ---" -ForegroundColor Cyan
if ($SkipBackendBuild) { Write-Warn "Build übersprungen." }
else {
  Push-Location (Join-Path $RepoRootResolved "backend")
  try {
    & npm install; if ($LASTEXITCODE -ne 0) { Write-Err "npm install fehlgeschlagen." } else { Write-Ok "npm install OK." }
    & npm run build; if ($LASTEXITCODE -ne 0) { Write-Err "Build fehlgeschlagen." } else { Write-Ok "Build OK." }
  } finally { Pop-Location }
}
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

if (-not $Target) { Write-Host "Nutzung: preflight.ps1 -Target <local|vps>" -ForegroundColor Cyan; exit 0 }
switch ($Target) {
  "local" { Invoke-LocalPreflight }
  "vps"   { Invoke-VpsPreflight }
}

Write-Host "=== Ergebnis ===" -ForegroundColor Cyan
Write-Host "Errors: $script:Errors  Warnings: $script:Warnings"
if ($script:Errors -gt 0) { exit 2 }
if ($script:Warnings -gt 0) { exit 1 }
exit 0
