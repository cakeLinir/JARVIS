param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$TaskName = "JARVIS Backend",
    [string]$TaskPath = "\JARVIS\",
    [string]$User = "",
    [switch]$AtLogon,
    [switch]$AtStartup
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

if (-not $AtLogon -and -not $AtStartup) {
    $AtLogon = $true
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$startScript = Join-Path $repoRootResolved "scripts\backend-start.ps1"

if (-not (Test-Path $startScript)) {
    Fail "backend-start.ps1 nicht gefunden: $startScript"
}

if (-not (Test-Path (Join-Path $repoRootResolved "backend\package.json"))) {
    Fail "backend\package.json nicht gefunden. RepoRoot falsch?"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$startScript`"",
    "-RepoRoot", "`"$repoRootResolved`"",
    "-Port", "8181"
) -join " "

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $arguments `
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
    -Description "Starts the JARVIS Fastify backend on Windows VPS."

Write-Info "Registriere Scheduled Task: $TaskPath$TaskName"

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -InputObject $task `
        -Force | Out-Null
}
catch {
    Fail "Scheduled Task konnte nicht registriert werden: $($_.Exception.Message)"
}

Write-Ok "Scheduled Task registriert: $TaskPath$TaskName"
Write-Host ""
Write-Host "Starten:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskPath `"$TaskPath`" -TaskName `"$TaskName`""
Write-Host ""
Write-Host "Status:" -ForegroundColor Cyan
Write-Host "  .\scripts\backend-task-status.ps1"
