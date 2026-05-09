param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$TaskName = "JARVIS Local Agent",
    [string]$TaskPath = "\JARVIS\",
    [string]$User = "",
    [switch]$AtStartup,
    [switch]$AtLogon
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

if (-not $AtStartup -and -not $AtLogon) {
    $AtLogon = $true
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$runner = Join-Path $repoRootResolved "scripts\run-local-agent.cmd"
$agentMain = Join-Path $repoRootResolved "desktop-agent\src\main.py"

if (-not (Test-Path $runner)) {
    Fail "CMD-Runner nicht gefunden: $runner"
}

if (-not (Test-Path $agentMain)) {
    Fail "desktop-agent\src\main.py nicht gefunden: $agentMain"
}

$action = New-ScheduledTaskAction `
    -Execute $runner `
    -WorkingDirectory $repoRootResolved

$triggers = @()

if ($AtStartup) {
    $triggers += New-ScheduledTaskTrigger -AtStartup
}

if ($AtLogon) {
    if ($User.Trim()) {
        $triggers += New-ScheduledTaskTrigger -AtLogOn -User $User
    }
    else {
        $triggers += New-ScheduledTaskTrigger -AtLogOn
    }
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

$principal = if ($User.Trim()) {
    New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
}
else {
    New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
}

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal `
    -Description "Starts the local JARVIS desktop agent via CMD runner."

Write-Info "Registriere lokale Agent Scheduled Task: $TaskPath$TaskName"

Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -InputObject $task `
    -Force | Out-Null

Write-Ok "Lokale Agent Scheduled Task registriert: $TaskPath$TaskName"
Write-Host ""
Write-Host "Manuell starten:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskPath `"$TaskPath`" -TaskName `"$TaskName`""
Write-Host ""
Write-Host "Status pruefen:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskPath `"$TaskPath`" -TaskName `"$TaskName`""
