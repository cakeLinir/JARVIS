param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$HealthUrl = "http://127.0.0.1:8181/api/health",
    [int]$TimeoutSeconds = 5,
    [int]$RestartDelaySeconds = 5,
    [switch]$BuildOnRestart
)

$ErrorActionPreference = "Stop"

$logsDir = Join-Path $RepoRoot "logs\backend-watchdog"
$logFile = Join-Path $logsDir "watchdog.log"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

function Write-WatchdogLog([string]$Level, [string]$Message) {
    $line = "$(Get-Date -Format o) [$Level] $Message"
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8

    switch ($Level) {
        "OK" { Write-Host "[$Level] $Message" -ForegroundColor Green }
        "WARN" { Write-Host "[$Level] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[$Level] $Message" -ForegroundColor Red }
        default { Write-Host "[$Level] $Message" }
    }
}

function Test-BackendHealth() {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec $TimeoutSeconds
        return ($response.status -eq "ok" -or $response.ok -eq $true)
    }
    catch {
        Write-WatchdogLog "WARN" "Healthcheck fehlgeschlagen: $HealthUrl | $($_.Exception.Message)"
        return $false
    }
}

Write-WatchdogLog "INFO" "Watchdog gestartet. RepoRoot=$RepoRoot HealthUrl=$HealthUrl"

if (Test-BackendHealth) {
    Write-WatchdogLog "OK" "Backend ist gesund."
    exit 0
}

$restartScript = Join-Path $RepoRoot "scripts\backend-restart.ps1"
if (-not (Test-Path $restartScript)) {
    Write-WatchdogLog "ERROR" "backend-restart.ps1 nicht gefunden: $restartScript"
    exit 2
}

Write-WatchdogLog "WARN" "Backend nicht gesund. Starte kontrollierten Restart."

if ($BuildOnRestart) {
    & $restartScript -RepoRoot $RepoRoot -Build -Force
}
else {
    & $restartScript -RepoRoot $RepoRoot -Force
}

if ($LASTEXITCODE -ne 0) {
    Write-WatchdogLog "ERROR" "Backend-Restart fehlgeschlagen. ExitCode=$LASTEXITCODE"
    exit 2
}

Start-Sleep -Seconds $RestartDelaySeconds

if (Test-BackendHealth) {
    Write-WatchdogLog "OK" "Backend nach Restart gesund."
    exit 0
}

Write-WatchdogLog "ERROR" "Backend nach Restart weiterhin nicht gesund."
exit 2
