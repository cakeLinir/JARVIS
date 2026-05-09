param(
    [string]$TaskName = "JARVIS Backend",
    [string]$TaskPath = "\JARVIS\"
)

$ErrorActionPreference = "Stop"

function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $task) {
    Write-Warn "Scheduled Task nicht gefunden: $TaskPath$TaskName"
    exit 1
}

Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
Write-Ok "Scheduled Task entfernt: $TaskPath$TaskName"
exit 0
