param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$Port = 8181
)

$ErrorActionPreference = "Stop"

$backendDir = Join-Path $RepoRoot "backend"
$pidFile = Join-Path $backendDir ".runtime\jarvis-backend.pid"
$healthUrl = "http://127.0.0.1:$Port/api/health"

Write-Host "=== JARVIS Backend Status ===" -ForegroundColor Cyan

if (Test-Path $pidFile) {
    $pidValue = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    Write-Host "PID file: $pidFile"
    Write-Host "PID:      $pidValue"

    if ($pidValue -and ($pidValue -as [int])) {
        $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "[OK] Prozess läuft: $($process.ProcessName) PID=$($process.Id)" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] PID-Datei vorhanden, aber Prozess läuft nicht." -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "[WARN] Keine PID-Datei gefunden." -ForegroundColor Yellow
}

$healthScript = Join-Path $RepoRoot "scripts\backend-health.ps1"
if (Test-Path $healthScript) {
    & $healthScript -Url $healthUrl -TimeoutSeconds 5
    exit $LASTEXITCODE
}

Write-Host "[WARN] backend-health.ps1 nicht gefunden." -ForegroundColor Yellow
exit 1
