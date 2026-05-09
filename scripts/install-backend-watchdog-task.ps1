param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$TaskName = "JARVIS Backend Watchdog",
    [string]$TaskPath = "\JARVIS\",
    [int]$EveryMinutes = 5,
    [string]$User = "",
    [switch]$BuildOnRestart
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$watchdogScript = Join-Path $repoRootResolved "scripts\backend-watchdog.ps1"

if (-not (Test-Path $watchdogScript)) {
    Fail "backend-watchdog.ps1 nicht gefunden: $watchdogScript"
}

if ($EveryMinutes -lt 1) {
    Fail "EveryMinutes muss mindestens 1 sein."
}

$args = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$watchdogScript`"",
    "-RepoRoot", "`"$repoRootResolved`""
)

if ($BuildOnRestart) {
    $args += "-BuildOnRestart"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($args -join " ") `
    -WorkingDirectory $repoRootResolved

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$trigger.Repetition.Interval = "PT${EveryMinutes}M"
$trigger.Repetition.Duration = "P3650D"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$principal = if ($User.Trim()) {
    New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
}
else {
    New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
}

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Checks JARVIS backend health and restarts it when unhealthy."

Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -InputObject $task -Force | Out-Null
Write-Ok "Watchdog Scheduled Task registriert: $TaskPath$TaskName"
