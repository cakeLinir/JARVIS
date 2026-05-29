<#
.SYNOPSIS  JARVIS Windows Scheduled Tasks – install | uninstall | status
.EXAMPLE   task.ps1 -Target backend  -Action install  -AtLogon
.EXAMPLE   task.ps1 -Target watchdog -Action install  -EveryMinutes 5
.EXAMPLE   task.ps1 -Target agent    -Action install  -AtLogon
.EXAMPLE   task.ps1 -Target backend  -Action status
#>
param(
    [Parameter(Position = 0)] [ValidateSet("backend","watchdog","agent")] [string]$Target,
    [Parameter(Position = 1)] [ValidateSet("install","uninstall","status")]  [string]$Action,
    [string]$RepoRoot      = (Resolve-Path ".").Path,
    [string]$TaskPath      = "\JARVIS\",
    [string]$User          = "",
    [switch]$AtLogon,
    [switch]$AtStartup,
    [int]   $EveryMinutes  = 5,
    [switch]$BuildOnRestart
)

$ErrorActionPreference = "Stop"
function Write-Info([string]$m)  { Write-Host "[INFO] $m"  -ForegroundColor Cyan  }
function Write-Ok([string]$m)    { Write-Host "[OK] $m"    -ForegroundColor Green }
function Write-Warn([string]$m)  { Write-Host "[WARN] $m"  -ForegroundColor Yellow}
function Fail([string]$m)        { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 2 }

$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$ScriptsDir       = Join-Path $RepoRootResolved "scripts"

function Get-Principal([string]$u) {
    if ($u.Trim()) { return New-ScheduledTaskPrincipal -UserId $u -LogonType Interactive -RunLevel Highest }
    return New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
}

function Get-LogonTriggers([switch]$startup, [switch]$logon, [string]$u) {
    if (-not $startup -and -not $logon) { $logon = $true }
    $t = @()
    if ($startup) { $t += New-ScheduledTaskTrigger -AtStartup }
    if ($logon) {
        if ($u.Trim()) { $t += New-ScheduledTaskTrigger -AtLogOn -User $u }
        else            { $t += New-ScheduledTaskTrigger -AtLogOn }
    }
    return $t
}

function Get-StandardSettings([int]$timeLimitHours = 0) {
    return New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours $timeLimitHours) `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable
}

function Show-TaskStatus([string]$name, [string]$path) {
    $task = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "[ERROR] Task nicht gefunden: $path$name" -ForegroundColor Red; exit 2 }
    $info = Get-ScheduledTaskInfo -TaskName $name -TaskPath $path
    Write-Host "=== $path$name ===" -ForegroundColor Cyan
    Write-Host "State:      $($task.State)"
    Write-Host "LastRun:    $($info.LastRunTime)"
    Write-Host "LastResult: $($info.LastTaskResult)"
    Write-Host "NextRun:    $($info.NextRunTime)"
    if ($task.State -in @("Ready","Running")) { Write-Ok "Task aktiv." } else { Write-Warn "State: $($task.State)" }
}

function Remove-JarvisTask([string]$name, [string]$path) {
    $task = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
    if (-not $task) { Write-Warn "Task nicht gefunden: $path$name. Nichts zu tun."; exit 0 }
    Unregister-ScheduledTask -TaskName $name -TaskPath $path -Confirm:$false
    Write-Ok "Task deinstalliert: $path$name"
}

# ── Backend Task ──────────────────────────────────────────────────────────────

function Install-BackendTask {
    $name      = "JARVIS Backend"
    $script    = Join-Path $ScriptsDir "04_backend.ps1"
    if (-not (Test-Path $script)) { Fail "04_backend.ps1 nicht gefunden: $script" }

    $taskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Action start -RepoRoot `"$RepoRootResolved`" -Port 8181"
    $action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs -WorkingDirectory $RepoRootResolved
    $triggers = Get-LogonTriggers -startup:$AtStartup -logon:$AtLogon -u $User
    $task     = New-ScheduledTask -Action $action -Trigger $triggers `
                    -Settings (Get-StandardSettings) `
                    -Principal (Get-Principal $User) `
                    -Description "Starts the JARVIS Fastify backend."
    Register-ScheduledTask -TaskName $name -TaskPath $TaskPath -InputObject $task -Force | Out-Null
    Write-Ok "Backend Task registriert: $TaskPath$name"
}

# ── Watchdog Task ─────────────────────────────────────────────────────────────

function Install-WatchdogTask {
    $name   = "JARVIS Backend Watchdog"
    $script = Join-Path $ScriptsDir "04_backend.ps1"
    if (-not (Test-Path $script)) { Fail "04_backend.ps1 nicht gefunden: $script" }
    if ($EveryMinutes -lt 1)      { Fail "EveryMinutes muss mindestens 1 sein." }

    $argParts = @("-NoProfile","-ExecutionPolicy","Bypass","-File","`"$script`"","-Action","watchdog-run","-RepoRoot","`"$RepoRootResolved`"")
    if ($BuildOnRestart) { $argParts += "-BuildOnRestart" }

    $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argParts -join " ") -WorkingDirectory $RepoRootResolved
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
                   -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
                   -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -MultipleInstances IgnoreNew -StartWhenAvailable
    $task     = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings `
                    -Principal (Get-Principal $User) -Description "Checks JARVIS backend health every $EveryMinutes min."
    Register-ScheduledTask -TaskName $name -TaskPath $TaskPath -InputObject $task -Force | Out-Null
    Write-Ok "Watchdog Task registriert: $TaskPath$name (alle $EveryMinutes Min.)"
}

# ── Agent Task ────────────────────────────────────────────────────────────────

function Install-AgentTask {
    $name    = "JARVIS Local Agent"
    $runner  = Join-Path $ScriptsDir "11_run-local-agent.cmd"
    $agentPy = Join-Path $RepoRootResolved "desktop-agent\src\main.py"
    if (-not (Test-Path $runner))  { Fail "11_run-local-agent.cmd nicht gefunden: $runner" }
    if (-not (Test-Path $agentPy)) { Fail "desktop-agent\src\main.py nicht gefunden." }

    $action   = New-ScheduledTaskAction -Execute $runner -WorkingDirectory $RepoRootResolved
    $triggers = Get-LogonTriggers -startup:$AtStartup -logon:$AtLogon -u $User
    $task     = New-ScheduledTask -Action $action -Trigger $triggers `
                    -Settings (Get-StandardSettings) `
                    -Principal (Get-Principal $User) `
                    -Description "Starts the local JARVIS desktop agent."
    Register-ScheduledTask -TaskName $name -TaskPath $TaskPath -InputObject $task -Force | Out-Null
    Write-Ok "Agent Task registriert: $TaskPath$name"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

if (-not $Target -or -not $Action) {
    Write-Host "Nutzung: task.ps1 -Target <backend|watchdog|agent> -Action <install|uninstall|status>" -ForegroundColor Cyan
    exit 0
}

switch ("$Target/$Action") {
    "backend/install"   { Install-BackendTask  }
    "backend/uninstall" { Remove-JarvisTask "JARVIS Backend"          $TaskPath }
    "backend/status"    { Show-TaskStatus   "JARVIS Backend"          $TaskPath }
    "watchdog/install"  { Install-WatchdogTask }
    "watchdog/uninstall"{ Remove-JarvisTask "JARVIS Backend Watchdog" $TaskPath }
    "watchdog/status"   { Show-TaskStatus   "JARVIS Backend Watchdog" $TaskPath }
    "agent/install"     { Install-AgentTask  }
    "agent/uninstall"   { Remove-JarvisTask "JARVIS Local Agent"      $TaskPath }
    "agent/status"      { Show-TaskStatus   "JARVIS Local Agent"      $TaskPath }
    default             { Write-Host "[ERROR] Unbekannte Kombination: $Target/$Action" -ForegroundColor Red; exit 2 }
}
