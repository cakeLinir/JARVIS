<#
.SYNOPSIS JARVIS Local Agent – start | stop | status | diagnose | config | todo-review
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet("start","stop","status","diagnose","config","todo-review")]
  [string]$Action,

  [string]$RepoRoot = (Resolve-Path ".").Path,
  [int] $LocalAgentPort = 8765,
  [string]$BackendUrl = "https://jarvis.hundekuchenlive.de",
  [string]$AgentName = "jarvis-desktop-agent",
  [string]$AgentToken = "",
  [switch]$ReadTokenFromBackendEnv,
  [switch]$ForceByPort,
  [switch]$WhatIfOnly,
  [string]$TodoPath = "",
  [switch]$ApplyToTodo,
  [int] $TimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$AgentDir = Join-Path $RepoRootResolved "desktop-agent"
$ScriptsDir = Join-Path $RepoRootResolved "scripts"

function Write-Info([string]$m) { Write-Host "[INFO] $m"  -ForegroundColor Cyan }
function Write-Ok([string]$m) { Write-Host "[OK] $m"    -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m"  -ForegroundColor Yellow }
function Write-Err([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red }
function Fail([string]$m) { Write-Err $m; exit 2 }

function Get-ConfigValue([object]$Config, [string[]]$Paths) {
  foreach ($path in $Paths) {
    $cur = $Config; $ok = $true
    foreach ($part in $path.Split(".")) {
      if ($null -eq $cur -or -not $cur.PSObject.Properties[$part]) { $ok = $false; break }
      $cur = $cur.$part
    }
    if ($ok -and $null -ne $cur -and "$cur".Trim()) { return "$cur" }
  }
  return ""
}

function Get-EnvValueFromFile([string]$Path, [string]$Key) {
  if (-not (Test-Path $Path)) { return "" }
  $line = Get-Content -LiteralPath $Path -Encoding UTF8 |
    Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } |
    Select-Object -First 1
  if (-not $line) { return "" }
  return ($line -replace "^\s*$([regex]::Escape($Key))\s*=\s*", "").Trim().Trim('"').Trim("'")
}

# ── Start ─────────────────────────────────────────────────────────────────────

function Start-Agent {
  $runner = Join-Path $ScriptsDir "11_run-local-agent.cmd"
  if (-not (Test-Path $runner)) { Fail "11_run-local-agent.cmd nicht gefunden: $runner" }
  Write-Info "Starte lokalen Agent..."
  Start-Process -FilePath $runner -WorkingDirectory $RepoRootResolved -WindowStyle Hidden
  Write-Ok "Agent gestartet (via run-local-agent.cmd)."
}

# ── Stop ──────────────────────────────────────────────────────────────────────

function Stop-Agent {
  $pidMap = @{}
  $cmdMatches = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
    $_.CommandLine -like "*desktop-agent*src*main.py*" -or
    $_.CommandLine -like "*$AgentDir*" -or
    ($_.CommandLine -like "*src*main.py*" -and $_.Name -match "^(python|pythonw|py)\.exe$")
    )
  }
  foreach ($p in $cmdMatches) { $pidMap["$($p.ProcessId)"] = $p }

  try {
    $conns = Get-NetTCPConnection -LocalPort $LocalAgentPort -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
      $owner = $c.OwningProcess
      if ($owner -and -not $pidMap.ContainsKey("$owner")) {
        $pi = try { Get-CimInstance Win32_Process -Filter "ProcessId=$owner" } catch { $null }
        if ($pi) { $pidMap["$owner"] = $pi }
      }
    }
  } catch {}

  if ($pidMap.Count -eq 0) { Write-Warn "Kein Agent-Prozess gefunden."; exit 1 }

  $stopped = 0; $skipped = 0
  foreach ($entry in $pidMap.GetEnumerator()) {
    $p = $entry.Value
    $procId = [int]$p.ProcessId
    $isAgent = ($p.CommandLine -like "*desktop-agent*src*main.py*") -or
    ($p.CommandLine -like "*$AgentDir*") -or
    ($p.CommandLine -like "*src*main.py*" -and $p.Name -match "^(python|pythonw|py)\.exe$")

    Write-Info "Gefunden: PID=$procId  Name=$($p.Name)"
    if (-not $isAgent -and -not $ForceByPort) {
      $skipped++; Write-Warn "Nicht eindeutig Agent. Nutze -ForceByPort zum Erzwingen."; continue
    }
    if ($WhatIfOnly) { Write-Info "[WHATIF] Würde PID=$procId stoppen."; continue }
    try { Stop-Process -Id $procId -Force; $stopped++; Write-Ok "Agent gestoppt: PID=$procId" }
  catch { Write-Warn "Konnte PID=$procId nicht stoppen: $($_.Exception.Message)" }
}
if ($WhatIfOnly) { exit 0 }
if ($stopped -gt 0) { exit 0 }
if ($skipped -gt 0) { exit 2 }
exit 1
}

# ── Status ────────────────────────────────────────────────────────────────────

function Get-AgentStatus {
  Write-Host "=== JARVIS Local Agent Status ===" -ForegroundColor Cyan
  $procs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*desktop-agent*src*main.py*"
  }
  if ($procs) {
    foreach ($p in $procs) { Write-Ok "Agent läuft: PID=$($p.ProcessId)  $($p.Name)" }
  } else {
    Write-Warn "Kein Agent-Prozess gefunden."
  }
  try {
    $health = Invoke-RestMethod "http://127.0.0.1:$LocalAgentPort/health" -TimeoutSec 3 -ErrorAction Stop
    if ($health.ok) { Write-Ok "Lokale Agent-API erreichbar. Status=$($health.runtime.status)" }
  } catch {
    Write-Warn "Lokale Agent-API nicht erreichbar (Port $LocalAgentPort)."
  }
}

# ── Diagnose ──────────────────────────────────────────────────────────────────

function Invoke-Diagnose {
  $configPath = Join-Path $RepoRootResolved "desktop-agent\config.local.json"
  if (-not (Test-Path $configPath)) { Fail "config.local.json nicht gefunden: $configPath" }
  $config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
  $baseUrl = if ($BackendUrl.Trim()) { $BackendUrl.Trim() } else { Get-ConfigValue $config @("backendUrl","backend.url") }
  $aToken = if ($AgentToken.Trim()) { $AgentToken.Trim() } else { Get-ConfigValue $config @("agentToken","backend.agentToken","agent.token") }
  $aName = if ($AgentName.Trim()) { $AgentName.Trim() } else { Get-ConfigValue $config @("agentName","agent.name") }
  if (-not $baseUrl) { Fail "BackendUrl fehlt." }
  $base = $baseUrl.TrimEnd("/")
  $uri = [Uri]$base
  Write-Host "=== JARVIS Agent Diagnose ===" -ForegroundColor Cyan
  Write-Host "BackendUrl: $base  |  Host: $($uri.Host)"
  try { $dns = Resolve-DnsName -Name $uri.Host -ErrorAction Stop; Write-Ok "DNS OK: $($dns.IPAddress -join ', ')" }
catch { Write-Err "DNS fehlgeschlagen: $($_.Exception.Message)" }
$port = if ($uri.Port -gt 0) { $uri.Port } elseif ($uri.Scheme -eq "https") { 443 } else { 80 }
try { $tcp = Test-NetConnection -ComputerName $uri.Host -Port $port -WarningAction SilentlyContinue; if ($tcp.TcpTestSucceeded) { Write-Ok "TCP OK: $($uri.Host):$port" } else { Write-Err "TCP fehlgeschlagen." } }
catch { Write-Err "TCP-Test fehlgeschlagen: $($_.Exception.Message)" }
try { $h = Invoke-RestMethod "$base/api/health" -TimeoutSec $TimeoutSeconds; Write-Ok "Health OK"; $h | ConvertTo-Json -Depth 4 }
catch { Write-Err "Health fehlgeschlagen: $($_.Exception.Message)" }
if ($aToken) {
  try {
    $body = @{ agentName=$aName; hostname=$env:COMPUTERNAME; status="online"; timestamp=(Get-Date).ToUniversalTime().ToString("o") } | ConvertTo-Json
    $resp = Invoke-RestMethod "$base/api/agent/status" -Method Post -Headers @{ Authorization="Bearer $aToken"; "Content-Type"="application/json" } -Body $body -TimeoutSec $TimeoutSeconds
    Write-Ok "Agent-Status POST erfolgreich."
  } catch { Write-Err "Agent-Status POST fehlgeschlagen: $($_.Exception.Message)" }
} else { Write-Warn "AgentToken fehlt; Agent-Status POST übersprungen." }
}

# ── Config ────────────────────────────────────────────────────────────────────

function Set-AgentConfig {
  $configPath = Join-Path $RepoRootResolved "desktop-agent\config.local.json"
  if (-not (Test-Path $configPath)) { Fail "config.local.json nicht gefunden: $configPath" }

  $token = $AgentToken.Trim()
  if (-not $token -and $ReadTokenFromBackendEnv) {
    $token = Get-EnvValueFromFile (Join-Path $RepoRootResolved "backend\.env") "JARVIS_AGENT_TOKEN"
    if ($token) { Write-Ok "Token aus backend\.env gelesen." }
  }
  if (-not $token) { Write-Warn "AgentToken nicht angegeben. Bestehender Wert bleibt." }

  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  Copy-Item -LiteralPath $configPath -Destination "$configPath.backup-$ts" -Force
  Write-Ok "Backup: $configPath.backup-$ts"

  $config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
  function Set-Prop($obj, $name, $val) {
    if ($obj.PSObject.Properties[$name]) { $obj.$name = $val } else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $val }
  }
  Set-Prop $config "backendUrl" $BackendUrl
  Set-Prop $config "agentName"  $AgentName
  if ($token) { Set-Prop $config "agentToken" $token }
  $config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $configPath -Encoding UTF8
  Write-Ok "Agent-Config aktualisiert. BackendUrl=$BackendUrl  AgentName=$AgentName"
  Write-Host "Testen: .\scripts\test.ps1 -Target connection" -ForegroundColor Cyan
}

# ── Todo-Review ───────────────────────────────────────────────────────────────

function Invoke-TodoReview {
  $commandModule = Join-Path $RepoRootResolved "desktop-agent\src\todo\todo_review_command.py"
  if (-not (Test-Path $commandModule)) { Fail "todo_review_command.py nicht gefunden: $commandModule" }
  $argsList = @($commandModule, "--repo-root", $RepoRootResolved)
  if ($TodoPath.Trim()) { $argsList += @("--todo", $TodoPath) }
  if ($ApplyToTodo) { $argsList += "--apply" }
  py -3 @argsList
  if ($LASTEXITCODE -ne 0) { Fail "Agent TODO Review fehlgeschlagen." }
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

if (-not $Action) {
  Write-Host "Nutzung: agent.ps1 -Action <start|stop|status|diagnose|config|todo-review>" -ForegroundColor Cyan
  exit 0
}
switch ($Action) {
  "start"       { Start-Agent }
  "stop"        { Stop-Agent }
  "status"      { Get-AgentStatus }
  "diagnose"    { Invoke-Diagnose }
  "config"      { Set-AgentConfig }
  "todo-review" { Invoke-TodoReview }
}
