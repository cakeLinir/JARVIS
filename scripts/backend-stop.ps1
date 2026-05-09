param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [switch]$Force
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

$backendDir = Join-Path $RepoRoot "backend"
$runtimeDir = Join-Path $backendDir ".runtime"
$pidFile = Join-Path $runtimeDir "jarvis-backend.pid"

Write-Host "=== JARVIS Backend Stop ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"

$stopped = $false

if (Test-Path $pidFile) {
    $pidValue = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)

    if ($pidValue -and ($pidValue -as [int])) {
        # Nicht $pid verwenden: $PID ist eine schreibgeschützte PowerShell-Automatikvariable.
        $backendPid = [int]$pidValue
        $backendProcess = Get-Process -Id $backendPid -ErrorAction SilentlyContinue

        if ($backendProcess) {
            Write-Info "Stoppe Backend PID=$backendPid..."
            Stop-Process -Id $backendPid -Force:$Force -ErrorAction Stop
            Start-Sleep -Seconds 1
            $stopped = $true
            Write-Ok "Backend-Prozess gestoppt. PID=$backendPid"
        }
        else {
            Write-Warn "PID-Datei vorhanden, aber Prozess läuft nicht: PID=$backendPid"
        }
    }
    else {
        Write-Warn "PID-Datei ist ungültig: $pidFile"
    }

    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if (-not $stopped) {
    Write-Info "Suche nach node-Prozessen mit dist/server.js..."
    $matches = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "^node(\.exe)?$" -and
            $_.CommandLine -match "dist[\\/]+server\.js" -and
            $_.CommandLine -match [regex]::Escape($backendDir)
        }

    foreach ($match in $matches) {
        Write-Info "Stoppe gefundenen Backend-Prozess PID=$($match.ProcessId)"
        Stop-Process -Id $match.ProcessId -Force:$Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
}

if ($stopped) {
    Write-Ok "Backend gestoppt."
    exit 0
}

Write-Warn "Kein laufender JARVIS Backend-Prozess gefunden."
exit 1
