param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$Port = 8181,
    [switch]$Build,
    [switch]$NoHealthCheck
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

function Test-CommandExists([string]$Command) {
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

$backendDir = Join-Path $RepoRoot "backend"
$runtimeDir = Join-Path $backendDir ".runtime"
$pidFile = Join-Path $runtimeDir "jarvis-backend.pid"
$logsDir = Join-Path $RepoRoot "logs\backend"
$distServer = Join-Path $backendDir "dist\server.js"

Write-Host "=== JARVIS Backend Start ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Backend:  $backendDir"
Write-Host "Port:     $Port"

if (-not (Test-Path $backendDir)) {
    Fail "Backend-Ordner nicht gefunden: $backendDir"
}

if (-not (Test-Path (Join-Path $backendDir "package.json"))) {
    Fail "backend\package.json nicht gefunden."
}

if (-not (Test-Path (Join-Path $backendDir ".env"))) {
    Write-Warn "backend\.env fehlt. Backend kann ohne echte Secrets nicht produktiv starten."
}

if (-not (Test-CommandExists "node")) {
    Fail "node ist nicht im PATH."
}

if (-not (Test-CommandExists "npm")) {
    Fail "npm ist nicht im PATH."
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

if (Test-Path $pidFile) {
    $existingPid = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($existingPid -and ($existingPid -as [int])) {
        $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Ok "Backend scheint bereits zu laufen. PID=$existingPid"
            exit 0
        }

        Write-Warn "PID-Datei existiert, aber Prozess läuft nicht mehr. Entferne stale PID-Datei."
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}

if ($Build -or -not (Test-Path $distServer)) {
    Write-Info "Baue Backend..."
    Push-Location $backendDir
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            Fail "npm run build fehlgeschlagen."
        }
    }
    finally {
        Pop-Location
    }
    Write-Ok "Backend Build erfolgreich."
}

if (-not (Test-Path $distServer)) {
    Fail "dist\server.js fehlt. Führe npm run build aus."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outLog = Join-Path $logsDir "backend-$timestamp.out.log"
$errLog = Join-Path $logsDir "backend-$timestamp.err.log"

Write-Info "Starte Backend-Prozess..."
$process = Start-Process `
    -FilePath "node" `
    -ArgumentList @("dist/server.js") `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $pidFile -Value ([string]$process.Id) -Encoding ASCII

Write-Ok "Backend gestartet. PID=$($process.Id)"
Write-Host "STDOUT: $outLog"
Write-Host "STDERR: $errLog"
Write-Host "PID:    $pidFile"

if (-not $NoHealthCheck) {
    Write-Info "Warte kurz auf Healthcheck..."
    Start-Sleep -Seconds 2

    $healthScript = Join-Path $RepoRoot "scripts\backend-health.ps1"
    if (Test-Path $healthScript) {
        & $healthScript -Url "http://127.0.0.1:$Port/api/health" -TimeoutSeconds 5
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Backend Healthcheck erfolgreich."
        }
        else {
            Write-Warn "Backend gestartet, aber Healthcheck war nicht erfolgreich. Prüfe Logs."
            exit 1
        }
    }
    else {
        Write-Warn "backend-health.ps1 nicht gefunden. Healthcheck übersprungen."
    }
}

exit 0
