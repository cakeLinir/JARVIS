<#
.SYNOPSIS  JARVIS Desktop-Agent - Autostart via Windows Task Scheduler
.DESCRIPTION
    Registriert den JARVIS Desktop-Agent als geplanten Task der beim Login startet.
    Nutzt pythonw.exe (kein Konsolenfenster). Idempotent - bestehender Task wird ersetzt.

.EXAMPLE  .\install-autostart.ps1              # installieren
.EXAMPLE  .\install-autostart.ps1 -Uninstall   # deinstallieren
.EXAMPLE  .\install-autostart.ps1 -Status      # Status anzeigen
.EXAMPLE  .\install-autostart.ps1 -StartNow    # installieren und sofort starten
#>
param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"

# Konstanten
$TaskFolder = "\"
$TaskName   = "JARVIS-Desktop-Agent"

$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AgentDir   = Join-Path $RepoRoot "desktop-agent"
$PythonW    = Join-Path $AgentDir ".venv\Scripts\pythonw.exe"
$MainPy     = Join-Path $AgentDir "src\main.py"
$LogDir     = Join-Path $RepoRoot "logs"

function Write-Ok($m)   { Write-Host " [OK]   $m" -ForegroundColor Green  }
function Write-Info($m) { Write-Host " [INFO] $m" -ForegroundColor Cyan   }
function Write-Warn($m) { Write-Host " [WARN] $m" -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host " [ERR]  $m" -ForegroundColor Red    }

function Get-AgentTask {
    return Get-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskName `
        -ErrorAction SilentlyContinue
}

# Status
if ($Status) {
    $task = Get-AgentTask
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskPath $TaskFolder -TaskName $TaskName
        Write-Ok  "Task: $TaskFolder$TaskName"
        Write-Info "Zustand:          $($task.State)"
        Write-Info "Letzter Lauf:     $($info.LastRunTime)"
        Write-Info "Letztes Ergebnis: $($info.LastTaskResult)"
        Write-Info "Naechster Lauf:   $($info.NextRunTime)"
    } else {
        Write-Warn "Task nicht installiert. Fuehre .\install-autostart.ps1 aus."
    }
    exit 0
}

# Deinstallation
if ($Uninstall) {
    $task = Get-AgentTask
    if ($task) {
        Unregister-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskName -Confirm:$false
        Write-Ok "Task entfernt: $TaskFolder$TaskName"
    } else {
        Write-Info "Task war nicht installiert."
    }
    exit 0
}

# Vorbedingungen pruefen
if (-not (Test-Path $PythonW)) {
    Write-Err "pythonw.exe nicht gefunden: $PythonW"
    Write-Info "Bitte erst ausfuehren:"
    Write-Info "  cd desktop-agent"
    Write-Info "  python -m venv .venv"
    Write-Info "  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path $MainPy)) {
    Write-Err "main.py nicht gefunden: $MainPy"
    exit 1
}

$configPath = Join-Path $AgentDir "config.local.json"
if (-not (Test-Path $configPath)) {
    Write-Warn "config.local.json fehlt in $AgentDir"
    Write-Info "Kopiere config.local.example.json und befuelle die Felder."
}

# logs/ sicherstellen
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Info "Logs-Ordner erstellt: $LogDir"
}

# Alten Task idempotent entfernen
$existing = Get-AgentTask
if ($existing) {
    Unregister-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskName -Confirm:$false
    Write-Info "Alter Task ersetzt."
}

# Task-Definition
$action = New-ScheduledTaskAction `
    -Execute $PythonW `
    -Argument "-u `"$MainPy`"" `
    -WorkingDirectory $AgentDir

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskPath $TaskFolder `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "JARVIS Desktop-Agent - startet automatisch beim Login" `
    -Force | Out-Null

Write-Ok  "Task registriert: $TaskFolder$TaskName"
Write-Info "Startet automatisch beim naechsten Windows-Login."
Write-Info "Agent-Verzeichnis: $AgentDir"
Write-Info "Logs:              $LogDir"
Write-Info ""
Write-Info "Weitere Befehle:"
Write-Info "  Status:         .\install-autostart.ps1 -Status"
Write-Info "  Sofort starten: .\install-autostart.ps1 -StartNow"
Write-Info "  Entfernen:      .\install-autostart.ps1 -Uninstall"

if ($StartNow) {
    Start-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskName
    Start-Sleep -Seconds 2
    $runState = (Get-AgentTask).State
    Write-Ok "Agent gestartet. Zustand: $runState"
}
