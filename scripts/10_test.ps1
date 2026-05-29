<#
.SYNOPSIS JARVIS Tests – connection | todo-review | agent-todo-review | morning-integration | project-analyzer | todos-api | shifts-api | streaming-api
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet("connection","todo-review","agent-todo-review","morning-integration","project-analyzer","todos-api","shifts-api","streaming-api")]
  [string]$Target,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$BackendUrl = "http://127.0.0.1:8181",
  [string]$AgentToken = "",
  [int] $TimeoutSeconds = 10,
  [switch]$ApplyToTodo,
  [string]$TodoPath = ""
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$script:Passed = 0; $script:Failed = 0

function Pass([string]$m) { $script:Passed++; Write-Host "[PASS] $m" -ForegroundColor Green }
function Fail([string]$m) { $script:Failed++; Write-Host "[FAIL] $m" -ForegroundColor Red }
function Info([string]$m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Err([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 2 }

function Get-Token {
  if ($AgentToken.Trim()) { return $AgentToken.Trim() }
  $envPath = Join-Path $RepoRootResolved "backend\.env"
  if (-not (Test-Path $envPath)) { return "" }
  foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
    if ($line.Trim() -match "^JARVIS_DASHBOARD_TOKEN=(.+)$") { return $Matches[1].Trim() }
  }
  return ""
}

function Get-Headers([string]$token) {
  return @{ "Authorization"="Bearer $token"; "Content-Type"="application/json"; "Accept"="application/json" }
}

# ── connection ────────────────────────────────────────────────────────────────

function Test-Connection {
  $configPath = Join-Path $RepoRootResolved "desktop-agent\config.local.json"
  if (-not (Test-Path $configPath)) { Err "config.local.json nicht gefunden." }
  $config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
  $base = if ($BackendUrl.Trim()) { $BackendUrl.TrimEnd("/") } else {
    $url = ""; foreach ($p in @("backendUrl","backend.url")) {
      $cur = $config; foreach ($part in $p.Split(".")) { if ($null -eq $cur -or -not $cur.PSObject.Properties[$part]) { $cur = $null; break }; $cur = $cur.$part }
      if ($cur) { $url = "$cur"; break }
    }; $url.TrimEnd("/")
  }
  $token = if ($AgentToken.Trim()) { $AgentToken.Trim() } else {
    $t = ""; foreach ($p in @("agentToken","backend.agentToken","agent.token")) {
      $cur = $config; foreach ($part in $p.Split(".")) { if ($null -eq $cur -or -not $cur.PSObject.Properties[$part]) { $cur = $null; break }; $cur = $cur.$part }
      if ($cur) { $t = "$cur"; break }
    }; $t
  }
  if (-not $base) { Err "BackendUrl fehlt." }
  if (-not $token) { Err "AgentToken fehlt." }
  Write-Host "=== VPS Connection Test === Backend: $base" -ForegroundColor Cyan
  $body = @{ agentName="jarvis-desktop-agent"; hostname=$env:COMPUTERNAME; status="online";
  timestamp=(Get-Date).ToUniversalTime().ToString("o"); source="test" } | ConvertTo-Json
  $headers = @{ Authorization="Bearer $token"; "Content-Type"="application/json" }
  try {
    $r = Invoke-RestMethod "$base/api/agent/status" -Method Post -Headers $headers -Body $body -TimeoutSec $TimeoutSeconds
    Pass "Agent-Status erfolgreich gesendet."
    $r | ConvertTo-Json -Depth 4
  } catch { Fail "Fehlgeschlagen: $($_.Exception.Message)"; exit 2 }
}

# ── todo-review ───────────────────────────────────────────────────────────────

function Test-TodoReview {
  $module = Join-Path $RepoRootResolved "desktop-agent\src\todo\todo_review.py"
  if (-not (Test-Path $module)) { Err "todo_review.py nicht gefunden." }
  $todoFile = if ($TodoPath.Trim()) { $TodoPath } else { Join-Path $RepoRootResolved "data\todo.md" }
  $reviewOut = Join-Path $RepoRootResolved "data\todo.review.json"
  $scheduleOut = Join-Path $RepoRootResolved "data\todo.schedule.json"
  if (-not (Test-Path $todoFile)) { Err "TODO-Datei nicht gefunden: $todoFile" }

  Info "Python Compile..."; py -3 -m py_compile $module; if ($LASTEXITCODE -ne 0) { Fail "py_compile fehlgeschlagen."; return }
  $pyArgs = @($module,"--todo",$todoFile,"--review-out",$reviewOut,"--schedule-out",$scheduleOut)
  if ($ApplyToTodo) {
    $backupDir = Join-Path (Split-Path $todoFile -Parent) "backups"
    $applyLog = Join-Path $RepoRootResolved "data\todo.apply-log.json"
    $pyArgs += @("--apply","--backup-dir",$backupDir,"--apply-log-out",$applyLog)
  }
  py -3 @pyArgs; if ($LASTEXITCODE -ne 0) { Fail "TODO Review fehlgeschlagen."; return }

  $r = Get-Content -LiteralPath $reviewOut -Raw | ConvertFrom-Json
  $s = Get-Content -LiteralPath $scheduleOut -Raw | ConvertFrom-Json
  if ($r.kind -eq "jarvis.todo.review") { Pass "Review kind OK." } else { Fail "Review kind falsch." }
  if ($s.kind -eq "jarvis.todo.schedule") { Pass "Schedule kind OK." } else { Fail "Schedule kind falsch." }
  if ($r.policy.applyAllowed -eq $true) { Pass "applyAllowed OK." } else { Fail "applyAllowed nicht true." }
}

# ── agent-todo-review ─────────────────────────────────────────────────────────

function Test-AgentTodoReview {
  $module = Join-Path $RepoRootResolved "desktop-agent\src\todo\todo_review_command.py"
  if (-not (Test-Path $module)) { Err "todo_review_command.py nicht gefunden." }
  $pyArgs = @($module,"--repo-root",$RepoRootResolved)
  if ($TodoPath.Trim()) { $pyArgs += @("--todo",$TodoPath) }
  if ($ApplyToTodo) { $pyArgs += "--apply" }
  py -3 @pyArgs
  if ($LASTEXITCODE -eq 0) { Pass "Agent TODO Review Command OK." } else { Fail "Agent TODO Review fehlgeschlagen." }
}

# ── morning-integration ───────────────────────────────────────────────────────

function Test-MorningIntegration {
  $module = Join-Path $RepoRootResolved "desktop-agent\src\todo\todo_review_command.py"
  if (-not (Test-Path $module)) { Err "todo_review_command.py nicht gefunden." }
  Info "Morning-TODO-Review Integration Test..."
  py -3 $module --repo-root $RepoRootResolved
  if ($LASTEXITCODE -eq 0) { Pass "Morning Integration OK." } else { Fail "Morning Integration fehlgeschlagen." }
}

# ── project-analyzer ──────────────────────────────────────────────────────────

function Test-ProjectAnalyzer {
  $module = Join-Path $RepoRootResolved "desktop-agent\src\integrations\project_analyzer.py"
  if (-not (Test-Path $module)) { Err "project_analyzer.py nicht gefunden." }
  Info "Python Compile project_analyzer.py..."; py -3 -m py_compile $module
  if ($LASTEXITCODE -ne 0) { Fail "py_compile fehlgeschlagen."; return }
  py -3 $module --repo-root $RepoRootResolved
  if ($LASTEXITCODE -eq 0) { Pass "Project Analyzer OK." } else { Fail "Project Analyzer fehlgeschlagen." }
}

# ── todos-api ─────────────────────────────────────────────────────────────────

function Test-TodosApi {
  $token = Get-Token; if (-not $token -or $token.ToUpper().Contains("CHANGE_ME")) { Err "JARVIS_DASHBOARD_TOKEN nicht konfiguriert." }
  $h = Get-Headers $token; $base = $BackendUrl.TrimEnd("/"); $createdId = $null
  Write-Host "=== Todo API Test === $base" -ForegroundColor Cyan

  Info "POST /api/todos"
  try { $r = Invoke-RestMethod "$base/api/todos" -Method Post -Headers $h -TimeoutSec $TimeoutSeconds `
    -Body (@{title="JARVIS Skript-Test $(Get-Date -Format 'HH:mm:ss')";priority=2;dueDate=(Get-Date).AddDays(1).ToString("yyyy-MM-dd");source="manual"}|ConvertTo-Json)
  if ($r.ok -and $r.todo.id) { $createdId=$r.todo.id; Pass "Todo erstellt: id=$createdId" } else { Fail "Keine id in Antwort." } }
catch { Fail "POST fehlgeschlagen: $($_.Exception.Message)" }

Info "GET /api/todos"
try { $r = Invoke-RestMethod "$base/api/todos?status=open" -Headers $h -TimeoutSec $TimeoutSeconds
if ($r.ok) { Pass "Liste: count=$($r.count)" } else { Fail "GET todos nicht ok." } }
catch { Fail "GET todos fehlgeschlagen: $($_.Exception.Message)" }

Info "GET /api/todos/due-today"
try { $r = Invoke-RestMethod "$base/api/todos/due-today" -Headers $h -TimeoutSec $TimeoutSeconds
if ($r.ok) { Pass "Due-Today: count=$($r.count)" } else { Fail "Due-Today nicht ok." } }
catch { Fail "Due-Today fehlgeschlagen: $($_.Exception.Message)" }

if ($createdId) {
  Info "PATCH + complete + reschedule + delete"
  try { $r = Invoke-RestMethod "$base/api/todos/$createdId" -Method Patch -Headers $h -TimeoutSec $TimeoutSeconds `
    -Body (@{priority=1}|ConvertTo-Json); if ($r.todo.priority -eq 1) { Pass "PATCH priority=1 OK." } else { Fail "PATCH priority falsch." } }
catch { Fail "PATCH: $($_.Exception.Message)" }
try { $r = Invoke-RestMethod "$base/api/todos/$createdId/complete" -Method Post -Headers $h -TimeoutSec $TimeoutSeconds `
  -Body (@{actor="manual"}|ConvertTo-Json); if ($r.todo.status -eq "done") { Pass "Complete OK." } else { Fail "Status nicht done." } }
catch { Fail "Complete: $($_.Exception.Message)" }
try { Invoke-RestMethod "$base/api/todos/$createdId" -Method Delete -Headers $h -TimeoutSec $TimeoutSeconds | Out-Null; Pass "Delete OK." }
catch { Fail "Delete: $($_.Exception.Message)" }
}
}

# ── shifts-api ────────────────────────────────────────────────────────────────

function Test-ShiftsApi {
  $token = Get-Token; if (-not $token -or $token.ToUpper().Contains("CHANGE_ME")) { Err "Token nicht konfiguriert." }
  $h = Get-Headers $token; $base = $BackendUrl.TrimEnd("/"); $createdId = $null
  $testDate = (Get-Date).AddDays(2).ToString("yyyy-MM-dd")
  Write-Host "=== Shift API Test === $base | Testdatum: $testDate" -ForegroundColor Cyan

  Info "POST Tagschicht"
  try { $r = Invoke-RestMethod "$base/api/shifts" -Method Post -Headers $h -TimeoutSec $TimeoutSeconds `
    -Body (@{date=$testDate;type="tag";source="manual";notes="test"}|ConvertTo-Json)
  if ($r.ok -and $r.shift.id) { $createdId=$r.shift.id; Pass "Tagschicht erstellt: $($r.shift.startTime)-$($r.shift.endTime)" } else { Fail "Keine shift.id." } }
catch { Fail "POST: $($_.Exception.Message)" }

Info "GET /api/shifts/$testDate"
try { $r = Invoke-RestMethod "$base/api/shifts/$testDate" -Headers $h -TimeoutSec $TimeoutSeconds
if ($r.ok -and $r.shift.type -eq "tag") { Pass "Schicht abrufbar." } else { Fail "Falscher Typ." } }
catch { Fail "GET date: $($_.Exception.Message)" }

Info "UPSERT Nachtschicht"
try { $r = Invoke-RestMethod "$base/api/shifts" -Method Post -Headers $h -TimeoutSec $TimeoutSeconds `
  -Body (@{date=$testDate;type="nacht";source="manual"}|ConvertTo-Json)
if ($r.ok -and $r.shift.overnight -eq $true) { Pass "Nachtschicht UPSERT OK, overnight=true, endDate=$($r.shift.endDate)" } else { Fail "UPSERT Nacht falsch." } }
catch { Fail "UPSERT: $($_.Exception.Message)" }

Info "GET today/tomorrow"
try { $r = Invoke-RestMethod "$base/api/shifts/today"    -Headers $h -TimeoutSec $TimeoutSeconds; if ($r.ok) { Pass "today OK." } else { Fail "today nicht ok." } }
catch { Fail "today: $($_.Exception.Message)" }
try { $r = Invoke-RestMethod "$base/api/shifts/tomorrow" -Headers $h -TimeoutSec $TimeoutSeconds; if ($r.ok) { Pass "tomorrow OK." } else { Fail "tomorrow nicht ok." } }
catch { Fail "tomorrow: $($_.Exception.Message)" }

if ($createdId) {
  try { Invoke-RestMethod "$base/api/shifts/$createdId" -Method Delete -Headers $h -TimeoutSec $TimeoutSeconds | Out-Null; Pass "Delete OK." }
catch { Fail "Delete: $($_.Exception.Message)" }
}
}

# ── streaming-api ─────────────────────────────────────────────────────────────

function Test-StreamingApi {
  $token = Get-Token; if (-not $token -or $token.ToUpper().Contains("CHANGE_ME")) { Err "Token nicht konfiguriert." }
  $h = Get-Headers $token; $base = $BackendUrl.TrimEnd("/"); $shiftIds = @()
  $today = (Get-Date).ToString("yyyy-MM-dd")
  $tomorrow = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")
  Write-Host "=== Streaming Advice API Test === $base" -ForegroundColor Cyan

  foreach ($entry in @(@{date=$today;type="tag"},@{date=$tomorrow;type="nacht"})) {
    try { $r = Invoke-RestMethod "$base/api/shifts" -Method Post -Headers $h -TimeoutSec $TimeoutSeconds `
      -Body (@{date=$entry.date;type=$entry.type;source="manual";notes="streaming-test"}|ConvertTo-Json)
    if ($r.ok) { $shiftIds += $r.shift.id; Pass "Testschicht: $($entry.type) $($entry.date)" } }
  catch { Fail "Testschicht anlegen: $($_.Exception.Message)" }
}

foreach ($url in @("$base/api/streaming/advice/today","$base/api/streaming/advice/tomorrow","$base/api/streaming/advice?date=$today")) {
  Info "GET $url"
  try { $r = Invoke-RestMethod $url -Headers $h -TimeoutSec $TimeoutSeconds
  if ($r.ok -and $r.advice.recommendation) { Pass "Advice OK: recommendation=$($r.advice.recommendation), score=$($r.advice.score)" }
else { Fail "Advice ohne recommendation." } }
catch { Fail "$url : $($_.Exception.Message)" }
}

Info "GET advice/week"
try { $r = Invoke-RestMethod "$base/api/streaming/advice/week" -Headers $h -TimeoutSec $TimeoutSeconds
if ($r.ok -and $r.count -eq 7) { Pass "Week: 7 Tage." } else { Fail "Week count=$($r.count)" } }
catch { Fail "Week: $($_.Exception.Message)" }

foreach ($id in $shiftIds) {
  try { Invoke-RestMethod "$base/api/shifts/$id" -Method Delete -Headers $h -TimeoutSec $TimeoutSeconds | Out-Null; Pass "Aufräum: $id" }
catch { Fail "Delete $id : $($_.Exception.Message)" }
}
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

Write-Host ""
if (-not $Target) {
  Write-Host "Nutzung: test.ps1 -Target <connection|todo-review|agent-todo-review|morning-integration|project-analyzer|todos-api|shifts-api|streaming-api>" -ForegroundColor Cyan
  exit 0
}
switch ($Target) {
  "connection"          { Test-Connection }
  "todo-review"         { Test-TodoReview }
  "agent-todo-review"   { Test-AgentTodoReview }
  "morning-integration" { Test-MorningIntegration }
  "project-analyzer"    { Test-ProjectAnalyzer }
  "todos-api"           { Test-TodosApi }
  "shifts-api"          { Test-ShiftsApi }
  "streaming-api"       { Test-StreamingApi }
}

Write-Host ""
Write-Host "Passed: $script:Passed" -ForegroundColor Green
Write-Host "Failed: $script:Failed" -ForegroundColor $(if ($script:Failed -gt 0) { "Red" } else { "Green" })
exit $(if ($script:Failed -gt 0) { 2 } else { 0 })
