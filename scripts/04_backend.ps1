<#
.SYNOPSIS  JARVIS Backend – start | stop | restart | status | health | cleanup | watchdog-run
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("start","stop","restart","status","health","cleanup","watchdog-run")]
    [string]$Action,

    [string]$RepoRoot          = (Resolve-Path ".").Path,
    [int]   $Port              = 8181,
    [switch]$Build,
    [switch]$Force,
    [switch]$Quiet,
    [switch]$NoHealthCheck,
    [switch]$BuildOnRestart,
    [int]   $KeepDays          = 14,
    [switch]$WhatIfOnly,
    [string]$HealthUrl         = ""
)

$ErrorActionPreference = "Stop"

# ── Shared ────────────────────────────────────────────────────────────────────

$BackendDir  = Join-Path $RepoRoot "backend"
$RuntimeDir  = Join-Path $BackendDir ".runtime"
$PidFile     = Join-Path $RuntimeDir "jarvis-backend.pid"
$DistServer  = Join-Path $BackendDir "dist\server.js"
$LogsDir     = Join-Path $RepoRoot "logs\backend"
$WatchdogLog = Join-Path $RepoRoot "logs\backend-watchdog\watchdog.log"
$EffectiveHealthUrl = if ($HealthUrl) { $HealthUrl } else { "http://127.0.0.1:$Port/api/health" }

function Write-Info([string]$m)  { Write-Host "[INFO] $m"  -ForegroundColor Cyan   }
function Write-Ok([string]$m)    { Write-Host "[OK] $m"    -ForegroundColor Green  }
function Write-Warn([string]$m)  { Write-Host "[WARN] $m"  -ForegroundColor Yellow }
function Write-Err([string]$m)   { Write-Host "[ERROR] $m" -ForegroundColor Red    }
function Fail([string]$m)        { Write-Err $m; exit 2 }
function Test-Cmd([string]$c)    { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

function Add-WatchdogLog([string]$Level, [string]$Message) {
    $dir = Split-Path $WatchdogLog -Parent
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $line = "$(Get-Date -Format o) [$Level] $Message"
    Add-Content -LiteralPath $WatchdogLog -Value $line -Encoding UTF8
    switch ($Level) {
        "OK"    { Write-Host "[$Level] $Message" -ForegroundColor Green  }
        "WARN"  { Write-Host "[$Level] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[$Level] $Message" -ForegroundColor Red    }
        default { Write-Host "[$Level] $Message" }
    }
}

# ── Health ────────────────────────────────────────────────────────────────────

function Invoke-BackendHealth {
    try {
        $r = Invoke-RestMethod -Uri $EffectiveHealthUrl -TimeoutSec 5
        if ($r.status -eq "ok" -or $r.ok -eq $true) {
            if (-not $Quiet) {
                Write-Ok "Backend Health OK: $EffectiveHealthUrl"
                $r | ConvertTo-Json -Depth 8
            }
            return $true
        }
        if (-not $Quiet) { Write-Warn "Health antwortet, aber Status nicht ok." }
        return $false
    } catch {
        if (-not $Quiet) { Write-Err "Backend nicht erreichbar: $EffectiveHealthUrl | $($_.Exception.Message)" }
        return $false
    }
}

# ── Start ─────────────────────────────────────────────────────────────────────

function Start-Backend {
    Write-Host "=== JARVIS Backend Start ===" -ForegroundColor Cyan
    if (-not (Test-Path $BackendDir))                             { Fail "Backend-Ordner fehlt: $BackendDir" }
    if (-not (Test-Path (Join-Path $BackendDir "package.json"))) { Fail "backend\package.json fehlt." }
    if (-not (Test-Path (Join-Path $BackendDir ".env")))         { Write-Warn "backend\.env fehlt." }
    if (-not (Test-Cmd "node"))                                   { Fail "node nicht im PATH." }
    if (-not (Test-Cmd "npm"))                                    { Fail "npm nicht im PATH." }

    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    New-Item -ItemType Directory -Path $LogsDir    -Force | Out-Null

    if (Test-Path $PidFile) {
        $existing = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($existing -and ($existing -as [int]) -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
            Write-Ok "Backend läuft bereits. PID=$existing"; exit 0
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }

    if ($Build -or -not (Test-Path $DistServer)) {
        Write-Info "Baue Backend..."
        Push-Location $BackendDir
        try { & npm run build; if ($LASTEXITCODE -ne 0) { Fail "npm run build fehlgeschlagen." } }
        finally { Pop-Location }
        Write-Ok "Build erfolgreich."
    }
    if (-not (Test-Path $DistServer)) { Fail "dist\server.js fehlt. Führe -Build aus." }

    $ts     = Get-Date -Format "yyyyMMdd-HHmmss"
    $outLog = Join-Path $LogsDir "backend-$ts.out.log"
    $errLog = Join-Path $LogsDir "backend-$ts.err.log"

    $proc = Start-Process -FilePath "node" -ArgumentList @("dist/server.js") `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
        -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $PidFile -Value ([string]$proc.Id) -Encoding ASCII

    Write-Ok "Backend gestartet. PID=$($proc.Id)"
    Write-Host "STDOUT: $outLog"
    Write-Host "STDERR: $errLog"

    if (-not $NoHealthCheck) {
        Write-Info "Warte auf Healthcheck..."
        Start-Sleep -Seconds 2
        $healthy = Invoke-BackendHealth
        if ($healthy) { Write-Ok "Healthcheck erfolgreich." }
        else          { Write-Warn "Backend gestartet, aber Healthcheck fehlgeschlagen. Prüfe Logs."; exit 1 }
    }
}

# ── Stop ──────────────────────────────────────────────────────────────────────

function Stop-Backend {
    Write-Host "=== JARVIS Backend Stop ===" -ForegroundColor Cyan
    $stopped = $false

    if (Test-Path $PidFile) {
        $pidVal = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pidVal -and ($pidVal -as [int])) {
            $backendPid  = [int]$pidVal
            $backendProc = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
            if ($backendProc) {
                Write-Info "Stoppe Backend PID=$backendPid..."
                Stop-Process -Id $backendPid -Force:$Force
                Start-Sleep -Seconds 1
                $stopped = $true
                Write-Ok "Backend gestoppt. PID=$backendPid"
            } else {
                Write-Warn "PID-Datei vorhanden, Prozess läuft nicht: PID=$backendPid"
            }
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }

    if (-not $stopped) {
        $matches = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match "^node(\.exe)?$" -and
            $_.CommandLine -match "dist[\\/]+server\.js" -and
            $_.CommandLine -match [regex]::Escape($BackendDir)
        }
        foreach ($m in $matches) {
            Stop-Process -Id $m.ProcessId -Force:$Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }

    if ($stopped) { Write-Ok "Backend gestoppt."; exit 0 }
    Write-Warn "Kein JARVIS Backend-Prozess gefunden."; exit 1
}

# ── Restart ───────────────────────────────────────────────────────────────────

function Restart-Backend {
    Write-Host "=== JARVIS Backend Restart ===" -ForegroundColor Cyan
    & $PSCommandPath -Action stop  -RepoRoot $RepoRoot -Force:$Force
    $stopExit = $LASTEXITCODE
    if ($stopExit -eq 2) { exit 2 }
    Start-Sleep -Seconds 2
    & $PSCommandPath -Action start -RepoRoot $RepoRoot -Port $Port -Build:$Build
    exit $LASTEXITCODE
}

# ── Status ────────────────────────────────────────────────────────────────────

function Get-BackendStatus {
    Write-Host "=== JARVIS Backend Status ===" -ForegroundColor Cyan
    if (Test-Path $PidFile) {
        $pidVal = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        Write-Host "PID-Datei: $PidFile  |  PID: $pidVal"
        if ($pidVal -and ($pidVal -as [int])) {
            $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
            if ($proc) { Write-Ok "Prozess läuft: $($proc.ProcessName) PID=$($proc.Id)" }
            else        { Write-Warn "PID-Datei vorhanden, Prozess läuft nicht." }
        }
    } else {
        Write-Warn "Keine PID-Datei gefunden."
    }
    $healthy = Invoke-BackendHealth
    exit $(if ($healthy) { 0 } else { 1 })
}

# ── Cleanup ───────────────────────────────────────────────────────────────────

function Clear-BackendLogs {
    Write-Host "=== JARVIS Log Cleanup ===" -ForegroundColor Cyan
    $cutoff  = (Get-Date).AddDays(-$KeepDays)
    $targets = @(
        (Join-Path $RepoRoot "logs\backend"),
        (Join-Path $RepoRoot "logs\backend-watchdog"),
        (Join-Path $RepoRoot "backend\data")
    )
    $deleted = 0; $matched = 0
    foreach ($target in $targets) {
        if (-not (Test-Path $target)) { continue }
        $files = Get-ChildItem -LiteralPath $target -Recurse -File | Where-Object {
            $_.LastWriteTime -lt $cutoff -and
            ($_.Extension -in @(".log",".jsonl",".txt") -or $_.Name -match "\.(err|out)\.log$")
        }
        foreach ($f in $files) {
            $matched++
            if ($WhatIfOnly) { Write-Host "[WHATIF] $($f.FullName)"; continue }
            Remove-Item -LiteralPath $f.FullName -Force
            $deleted++
            Write-Ok "Gelöscht: $($f.FullName)"
        }
    }
    Write-Host "Gefunden: $matched  |  Gelöscht: $deleted"
}

# ── Watchdog ──────────────────────────────────────────────────────────────────

function Invoke-Watchdog {
    Add-WatchdogLog "INFO" "Watchdog gestartet. RepoRoot=$RepoRoot HealthUrl=$EffectiveHealthUrl"
    $healthy = Invoke-BackendHealth
    if ($healthy) { Add-WatchdogLog "OK" "Backend ist gesund."; exit 0 }

    Add-WatchdogLog "WARN" "Backend nicht gesund. Starte kontrollierten Restart."
    & $PSCommandPath -Action restart -RepoRoot $RepoRoot -Build:$BuildOnRestart -Force
    if ($LASTEXITCODE -ne 0) { Add-WatchdogLog "ERROR" "Restart fehlgeschlagen."; exit 2 }

    Start-Sleep -Seconds 5
    $healthyAfter = Invoke-BackendHealth
    if ($healthyAfter) { Add-WatchdogLog "OK" "Backend nach Restart gesund."; exit 0 }
    Add-WatchdogLog "ERROR" "Backend nach Restart weiterhin nicht gesund."; exit 2
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

if (-not $Action) {
    Write-Host "Nutzung: backend.ps1 -Action <start|stop|restart|status|health|cleanup|watchdog-run>" -ForegroundColor Cyan
    exit 0
}
switch ($Action) {
    "start"        { Start-Backend   }
    "stop"         { Stop-Backend    }
    "restart"      { Restart-Backend }
    "status"       { Get-BackendStatus }
    "health"       { $ok = Invoke-BackendHealth; exit $(if ($ok) { 0 } else { 2 }) }
    "cleanup"      { Clear-BackendLogs }
    "watchdog-run" { Invoke-Watchdog   }
}
