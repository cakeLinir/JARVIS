param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$ExpectedPort = 8181,
    [switch]$SkipBackendBuild
)

$ErrorActionPreference = "Stop"

$script:Errors = 0
$script:Warnings = 0

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    $script:Warnings += 1
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorStatus([string]$Message) {
    $script:Errors += 1
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-ConfigRequired([string]$Message) {
    $script:Warnings += 1
    Write-Host "[KONFIGURATION_ERFORDERLICH] $Message" -ForegroundColor Yellow
}

function Test-CommandExists([string]$Command) {
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Read-EnvFile([string]$Path) {
    $result = @{}

    if (-not (Test-Path $Path)) {
        return $result
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $index = $trimmed.IndexOf("=")
        if ($index -le 0) {
            continue
        }

        $key = $trimmed.Substring(0, $index).Trim()
        $value = $trimmed.Substring($index + 1).Trim()
        $result[$key] = $value
    }

    return $result
}

function Test-SecretConfigured([hashtable]$EnvMap, [string]$Key) {
    if (-not $EnvMap.ContainsKey($Key)) {
        Write-ConfigRequired "$Key fehlt."
        return
    }

    $value = [string]$EnvMap[$Key]
    $upper = $value.ToUpperInvariant()

    if (-not $value -or $upper.Contains("CHANGE_ME") -or $upper.Contains("PLACEHOLDER") -or $upper.Contains("EXAMPLE")) {
        Write-ConfigRequired "$Key ist noch nicht echt gesetzt."
        return
    }

    Write-Ok "$Key ist gesetzt."
}

function Test-GitTracked([string]$RelativePath) {
    Push-Location $RepoRoot
    try {
        & git ls-files --error-unmatch -- $RelativePath *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        Pop-Location
    }
}

Write-Host "=== JARVIS VPS Preflight ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"
Write-Host "ExpectedPort: $ExpectedPort"

if (-not (Test-Path $RepoRoot)) {
    Write-ErrorStatus "RepoRoot existiert nicht: $RepoRoot"
    exit 2
}

$requiredPaths = @(
    "backend\package.json",
    "backend\src\server.ts",
    "backend\.env",
    "docs"
)

foreach ($relative in $requiredPaths) {
    $path = Join-Path $RepoRoot $relative
    if (Test-Path $path) {
        Write-Ok "Gefunden: $relative"
    }
    else {
        if ($relative -eq "backend\.env") {
            Write-ConfigRequired "backend\.env fehlt auf dem VPS."
        }
        else {
            Write-ErrorStatus "Fehlt: $relative"
        }
    }
}

$desktopAgentPath = Join-Path $RepoRoot "desktop-agent\src\main.py"
if (Test-Path $desktopAgentPath) {
    Write-Ok "Gefunden: desktop-agent\src\main.py"
}
else {
    Write-Warn "Optional fehlt: desktop-agent\src\main.py (auf dem VPS nur erforderlich, wenn der lokale Agent dort bewusst mit deployed wird)"
}

Write-Host ""
Write-Host "--- Tooling ---" -ForegroundColor Cyan

if (Test-CommandExists "node") {
    Write-Ok "Node verfügbar: $(& node --version)"
}
else {
    Write-ErrorStatus "Node.js ist nicht im PATH."
}

if (Test-CommandExists "npm") {
    Write-Ok "npm verfügbar: $(& npm --version)"
}
else {
    Write-ErrorStatus "npm ist nicht im PATH."
}

if (Test-CommandExists "py") {
    Write-Ok "Python Launcher verfügbar: $(& py -3 --version)"
}
elseif (Test-CommandExists "python") {
    Write-Ok "python verfügbar: $(& python --version)"
}
else {
    Write-Warn "Python wurde nicht gefunden. Für reinen VPS-Backend-Betrieb ist das nur relevant, wenn Agent/Bot dort geprüft werden sollen."
}

Write-Host ""
Write-Host "--- Git Runtime-Dateien ---" -ForegroundColor Cyan

$backendDataDir = Join-Path $RepoRoot "backend\data"
if (-not (Test-Path $backendDataDir)) {
    New-Item -ItemType Directory -Path $backendDataDir -Force | Out-Null
    Write-Ok "Runtime-Ordner erstellt: backend\data"
}
else {
    Write-Ok "Runtime-Ordner vorhanden: backend\data"
}

$gitkeepPath = Join-Path $backendDataDir ".gitkeep"
if (-not (Test-Path $gitkeepPath)) {
    New-Item -ItemType File -Path $gitkeepPath -Force | Out-Null
    Write-Ok "Platzhalter erstellt: backend\data\.gitkeep"
}
else {
    Write-Ok "Platzhalter vorhanden: backend\data\.gitkeep"
}

$runtimePaths = @(
    "backend/data/commands.json",
    "backend/data/audit-log.jsonl"
)

foreach ($relative in $runtimePaths) {
    $path = Join-Path $RepoRoot ($relative -replace "/", "\")
    $tracked = Test-GitTracked $relative

    if ($tracked) {
        Write-Warn "$relative ist von Git getrackt. Runtime-Dateien sollten nicht committed werden."
    }
    elseif (Test-Path $path) {
        Write-Ok "$relative existiert lokal und ist nicht getrackt."
    }
    else {
        Write-Ok "$relative existiert noch nicht und ist nicht getrackt."
    }
}

if (Test-GitTracked "backend/data/.gitkeep") {
    Write-Ok "backend/data/.gitkeep ist getrackt."
}
else {
    Write-Warn "backend/data/.gitkeep ist noch nicht getrackt. Lokal committen/pushen, damit backend/data/ auf dem VPS vorhanden bleibt."
}

Write-Host ""
Write-Host "--- Port Prüfung ---" -ForegroundColor Cyan

try {
    $connection = Get-NetTCPConnection -LocalPort $ExpectedPort -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Warn "Port $ExpectedPort ist bereits belegt. Prüfe, ob das JARVIS Backend bereits läuft."
        $connection | Select-Object -First 5 LocalAddress,LocalPort,State,OwningProcess | Format-Table | Out-String | Write-Host
    }
    else {
        Write-Ok "Port $ExpectedPort ist aktuell frei."
    }
}
catch {
    Write-Warn "Portprüfung über Get-NetTCPConnection nicht möglich: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "--- Backend .env ---" -ForegroundColor Cyan

$backendEnvPath = Join-Path $RepoRoot "backend\.env"
if (Test-Path $backendEnvPath) {
    $backendEnv = Read-EnvFile $backendEnvPath

    Test-SecretConfigured $backendEnv "OPENAI_API_KEY"
    Test-SecretConfigured $backendEnv "JARVIS_AGENT_TOKEN"
    Test-SecretConfigured $backendEnv "JARVIS_BOT_BRIDGE_TOKEN"
    Test-SecretConfigured $backendEnv "JARVIS_DASHBOARD_TOKEN"

    if ($backendEnv.ContainsKey("JARVIS_BACKEND_PORT")) {
        if ([string]$backendEnv["JARVIS_BACKEND_PORT"] -eq [string]$ExpectedPort) {
            Write-Ok "JARVIS_BACKEND_PORT entspricht $ExpectedPort."
        }
        else {
            Write-Warn "JARVIS_BACKEND_PORT entspricht nicht $ExpectedPort."
        }
    }
    else {
        Write-Warn "JARVIS_BACKEND_PORT fehlt in backend\.env."
    }
}

Write-Host ""
Write-Host "--- Backend Build ---" -ForegroundColor Cyan

if ($SkipBackendBuild) {
    Write-Warn "Backend Build wurde übersprungen."
}
elseif ((Test-Path (Join-Path $RepoRoot "backend\package.json")) -and (Test-CommandExists "npm")) {
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorStatus "npm install fehlgeschlagen. ExitCode=$LASTEXITCODE"
        }
        else {
            Write-Ok "npm install erfolgreich."
        }

        & npm run build
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorStatus "npm run build fehlgeschlagen. ExitCode=$LASTEXITCODE"
        }
        else {
            Write-Ok "npm run build erfolgreich."
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-ErrorStatus "Backend Build nicht möglich: package.json oder npm fehlt."
}

Write-Host ""
Write-Host "=== Ergebnis ===" -ForegroundColor Cyan
Write-Host "Errors: $script:Errors"
Write-Host "Warnings: $script:Warnings"

if ($script:Errors -gt 0) {
    exit 2
}

if ($script:Warnings -gt 0) {
    exit 1
}

exit 0
