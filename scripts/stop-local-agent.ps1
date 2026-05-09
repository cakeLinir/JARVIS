param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$LocalAgentPort = 8765,
    [switch]$WhatIfOnly,
    [switch]$ForceByPort
)

$ErrorActionPreference = "Stop"

function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$agentDir = Join-Path $repoRootResolved "desktop-agent"

function Get-ProcessInfoById([int]$TargetPid) {
    try {
        return Get-CimInstance Win32_Process -Filter "ProcessId=$TargetPid"
    }
    catch {
        return $null
    }
}

function Test-IsAgentProcess($ProcessInfo) {
    if (-not $ProcessInfo) {
        return $false
    }

    $commandLine = "$($ProcessInfo.CommandLine)"
    $name = "$($ProcessInfo.Name)"

    if ($commandLine -like "*desktop-agent*src*main.py*") {
        return $true
    }

    if ($commandLine -like "*$agentDir*") {
        return $true
    }

    if ($commandLine -like "*src*main.py*" -and $name -match "^(python|pythonw|py)\.exe$") {
        return $true
    }

    return $false
}

$pidMap = @{}

$commandLineMatches = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        (
            $_.CommandLine -like "*desktop-agent*src*main.py*" -or
            $_.CommandLine -like "*$agentDir*" -or
            ($_.CommandLine -like "*src*main.py*" -and $_.Name -match "^(python|pythonw|py)\.exe$")
        )
    }

foreach ($process in $commandLineMatches) {
    $pidMap["$($process.ProcessId)"] = $process
}

try {
    $connections = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $LocalAgentPort -State Listen -ErrorAction SilentlyContinue

    if (-not $connections) {
        $connections = Get-NetTCPConnection -LocalPort $LocalAgentPort -State Listen -ErrorAction SilentlyContinue
    }

    foreach ($connection in $connections) {
        $owner = $connection.OwningProcess
        if ($owner -and -not $pidMap.ContainsKey("$owner")) {
            $processInfo = Get-ProcessInfoById -TargetPid $owner
            if ($processInfo) {
                $pidMap["$owner"] = $processInfo
            }
        }
    }
}
catch {
    Write-Warn "Port-Erkennung über Get-NetTCPConnection fehlgeschlagen: $($_.Exception.Message)"
}

if ($pidMap.Count -eq 0) {
    Write-Warn "Kein lokaler JARVIS Agent-Prozess gefunden."
    exit 1
}

$stopped = 0
$skipped = 0

foreach ($entry in $pidMap.GetEnumerator()) {
    $process = $entry.Value
    $targetPid = [int]$process.ProcessId
    $isAgent = Test-IsAgentProcess $process

    Write-Info "Gefunden: PID=$targetPid Name=$($process.Name)"
    Write-Host "CommandLine: $($process.CommandLine)"

    if (-not $isAgent -and -not $ForceByPort) {
        $skipped += 1
        Write-Warn "Prozess besitzt Port $LocalAgentPort, sieht aber nicht eindeutig nach JARVIS Agent aus. Übersprungen."
        Write-Host "Zum Erzwingen:"
        Write-Host "  .\scripts\stop-local-agent.ps1 -ForceByPort"
        continue
    }

    if ($WhatIfOnly) {
        Write-Info "WhatIfOnly aktiv. Würde PID=$targetPid stoppen."
        continue
    }

    try {
        Stop-Process -Id $targetPid -Force
        $stopped += 1
        Write-Ok "Agent-Prozess gestoppt: PID=$targetPid"
    }
    catch {
        Write-Warn "Agent-Prozess konnte nicht gestoppt werden: PID=$targetPid | $($_.Exception.Message)"
    }
}

if ($WhatIfOnly) {
    exit 0
}

if ($stopped -gt 0) {
    exit 0
}

if ($skipped -gt 0) {
    exit 2
}

exit 1
