param(
    [string]$TaskName = "JARVIS Backend Watchdog",
    [string]$TaskPath = "\JARVIS\"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $task) {
    Write-Host "[WARN] Watchdog Scheduled Task nicht gefunden: $TaskPath$TaskName" -ForegroundColor Yellow
    exit 1
}

Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
Write-Host "[OK] Watchdog Scheduled Task entfernt: $TaskPath$TaskName" -ForegroundColor Green
exit 0
