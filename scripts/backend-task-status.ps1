param(
    [string]$TaskName = "JARVIS Backend",
    [string]$TaskPath = "\JARVIS\"
)

$ErrorActionPreference = "Stop"

function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-ErrorStatus([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red }

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $task) {
    Write-ErrorStatus "Scheduled Task nicht gefunden: $TaskPath$TaskName"
    exit 2
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

Write-Host "=== JARVIS Backend Scheduled Task ===" -ForegroundColor Cyan
Write-Host "Name:       $TaskPath$TaskName"
Write-Host "State:      $($task.State)"
Write-Host "LastRun:    $($info.LastRunTime)"
Write-Host "LastResult: $($info.LastTaskResult)"
Write-Host "NextRun:    $($info.NextRunTime)"

if ($task.State -eq "Ready" -or $task.State -eq "Running") {
    Write-Ok "Scheduled Task vorhanden."
}
else {
    Write-Warn "Scheduled Task vorhanden, aber Status ist $($task.State)."
}

exit 0
