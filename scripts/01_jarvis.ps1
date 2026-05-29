<#
.SYNOPSIS JARVIS Operations CLI — zentraler Einstiegspunkt
.EXAMPLE .\scripts\jarvis.ps1 backend start -Build
.EXAMPLE .\scripts\jarvis.ps1 task backend install -AtLogon
.EXAMPLE .\scripts\jarvis.ps1 test todos-api
#>
param(
  [Parameter(Position = 0)] [string]$Area,
  [Parameter(Position = 1)] [string]$Action,
  [Parameter(Position = 2)] [string]$SubAction,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  # Backend
  [switch]$Build,
  [switch]$Force,
  [switch]$Quiet,
  [switch]$NoHealthCheck,
  [switch]$BuildOnRestart,
  [int] $KeepDays = 14,
  [switch]$WhatIfOnly,
  # Task
  [switch]$AtLogon,
  [switch]$AtStartup,
  [int] $EveryMinutes = 5,
  # Dashboard / Caddy
  [switch]$ReloadCaddy,
  [switch]$Reload,
  # Config
  [string]$Domain = "jarvis.hundekuchenlive.de",
  [int] $Port = 8181,
  [switch]$AllowInsecurePublicHttp,
  [switch]$ApplyPull,
  # VPS
  [string]$Branch = "main",
  [switch]$SkipGitPull,
  [switch]$SkipInstall,
  [switch]$SkipBackendBuild,
  [switch]$SkipDashboardBuild,
  [switch]$SkipCaddyReload,
  [switch]$AllowDirty,
  # Agent
  [string]$BackendUrl = "https://jarvis.hundekuchenlive.de",
  [string]$AgentName = "jarvis-desktop-agent",
  [string]$AgentToken = "",
  [switch]$ReadTokenFromBackendEnv,
  [switch]$ForceByPort,
  [string]$TodoPath = "",
  [switch]$ApplyToTodo,
  # Preflight
  [int] $ExpectedPort = 8181,
  [switch]$SkipAgentCompile,
  [switch]$CheckLocalApi,
  # Test
  [int] $TimeoutSeconds = 10
)

$ErrorActionPreference = "Stop"
$ScriptsDir = Join-Path (Resolve-Path $RepoRoot).Path "scripts"

function Invoke-Sub([string]$Script, [hashtable]$Params = @{}) {
  $path = Join-Path $ScriptsDir $Script
  if (-not (Test-Path $path)) { Write-Host "[ERROR] Skript nicht gefunden: $Script" -ForegroundColor Red; exit 2 }
  & $path @Params; exit $LASTEXITCODE
}

function Write-Usage {
  Write-Host "JARVIS CLI" -ForegroundColor Cyan
  Write-Host ""
  Write-Host "backend  start [-Build] | stop [-Force] | restart [-Build] | status | health | cleanup [-KeepDays N] | watchdog-run"
  Write-Host "task     <backend|watchdog|agent>  <install [-AtLogon|-AtStartup] | uninstall | status>"
  Write-Host "agent    start | stop | status | diagnose | config [-BackendUrl ..] | todo-review [-ApplyToTodo]"
  Write-Host "dashboard  build | deploy [-ReloadCaddy] | check"
  Write-Host "caddy    install [-Reload] | health"
  Write-Host "config   https | public -AllowInsecurePublicHttp | vps-sparse [-ApplyPull]"
  Write-Host "vps      update-backend | update-project | check-layout"
  Write-Host "preflight  local | vps"
  Write-Host "test     connection | todo-review | agent-todo-review | morning-integration | project-analyzer | todos-api | shifts-api | streaming-api"
  Write-Host ""
}

if (-not $Area -or $Area -in @("help","-h","--help","/?")) { Write-Usage; exit 0 }

$areaKey = $Area.Trim().ToLowerInvariant()
$actionKey = $Action.Trim().ToLowerInvariant()

switch ($areaKey) {
  "backend" {
    $a = @{ Action=$actionKey; RepoRoot=$RepoRoot; Port=$Port; Build=$Build; Force=$Force;
    Quiet=$Quiet; NoHealthCheck=$NoHealthCheck; BuildOnRestart=$BuildOnRestart;
    KeepDays=$KeepDays; WhatIfOnly=$WhatIfOnly }
    Invoke-Sub "04_backend.ps1" $a
  }
  "task" {
    # jarvis.ps1 task backend install → Area=task, Action=backend, SubAction=install (Position 2)
    $taskTarget = $actionKey
    $taskAction = $SubAction.Trim().ToLowerInvariant()
    if (-not $taskAction) { Write-Usage; exit 2 }
    $a = @{ Target=$taskTarget; Action=$taskAction; RepoRoot=$RepoRoot;
    AtLogon=$AtLogon; AtStartup=$AtStartup; EveryMinutes=$EveryMinutes; BuildOnRestart=$BuildOnRestart }
    Invoke-Sub "07_task.ps1" $a
  }
  "agent" {
    $a = @{ Action=$actionKey; RepoRoot=$RepoRoot; BackendUrl=$BackendUrl;
    AgentName=$AgentName; AgentToken=$AgentToken;
    ReadTokenFromBackendEnv=$ReadTokenFromBackendEnv;
    ForceByPort=$ForceByPort; WhatIfOnly=$WhatIfOnly;
    TodoPath=$TodoPath; ApplyToTodo=$ApplyToTodo; TimeoutSeconds=$TimeoutSeconds }
    Invoke-Sub "08_agent.ps1" $a
  }
  "dashboard" {
    Invoke-Sub "06_dashboard.ps1" @{ Action=$actionKey; RepoRoot=$RepoRoot; ReloadCaddy=$ReloadCaddy }
  }
  "caddy" {
    Invoke-Sub "05_caddy.ps1" @{ Action=$actionKey; RepoRoot=$RepoRoot; Reload=$Reload }
  }
  "config" {
    # BugFix: BackendUrl/AgentName/AgentToken/ReadTokenFromBackendEnv existieren in config.ps1 nicht
    $a = @{ Action=$actionKey; RepoRoot=$RepoRoot; Domain=$Domain; Port=$Port;
    AllowInsecurePublicHttp=$AllowInsecurePublicHttp; ApplyPull=$ApplyPull }
    Invoke-Sub "02_config.ps1" $a
  }
  "vps" {
    $a = @{ Action=$actionKey; RepoRoot=$RepoRoot; Branch=$Branch;
    SkipGitPull=$SkipGitPull; SkipInstall=$SkipInstall;
    SkipBackendBuild=$SkipBackendBuild; SkipDashboardBuild=$SkipDashboardBuild;
    SkipCaddyReload=$SkipCaddyReload; AllowDirty=$AllowDirty }
    Invoke-Sub "09_vps.ps1" $a
  }
  "preflight" {
    $a = @{ Target=$actionKey; RepoRoot=$RepoRoot; ExpectedPort=$ExpectedPort;
    SkipBackendBuild=$SkipBackendBuild; SkipAgentCompile=$SkipAgentCompile;
    CheckLocalApi=$CheckLocalApi }
    Invoke-Sub "03_preflight.ps1" $a
  }
  "test" {
    $a = @{ Target=$actionKey; RepoRoot=$RepoRoot; BackendUrl=$BackendUrl;
    AgentToken=$AgentToken; TimeoutSeconds=$TimeoutSeconds;
    ApplyToTodo=$ApplyToTodo; TodoPath=$TodoPath }
    Invoke-Sub "10_test.ps1" $a
  }
  default { Write-Usage; exit 2 }
}
