param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [switch]$SkipBackendBuild,
    [switch]$SkipAgentCompile,
    [switch]$CheckLocalApi,
    [string]$LocalApiUrl = "http://127.0.0.1:8765/health"
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

function Test-RequiredPath([string]$RelativePath, [string]$Description) {
    $path = Join-Path $RepoRoot $RelativePath
    if (Test-Path $path) {
        Write-Ok "$Description gefunden: $RelativePath"
        return $true
    }

    Write-ErrorStatus "$Description fehlt: $RelativePath"
    return $false
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

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path $Path)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $Path -Encoding UTF8 -Raw | ConvertFrom-Json
    }
    catch {
        Write-ErrorStatus "JSON konnte nicht gelesen werden: $Path | $($_.Exception.Message)"
        return $null
    }
}

Write-Host "=== JARVIS Local Preflight ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"

if (-not (Test-Path $RepoRoot)) {
    Write-ErrorStatus "RepoRoot existiert nicht: $RepoRoot"
    exit 2
}

Test-RequiredPath "README.md" "README" | Out-Null
Test-RequiredPath "backend\package.json" "Backend package.json" | Out-Null
Test-RequiredPath "backend\src\server.ts" "Backend Server" | Out-Null
Test-RequiredPath "desktop-agent\src\main.py" "Desktop-Agent main.py" | Out-Null
Test-RequiredPath "desktop-agent\config.json" "Desktop-Agent config.json" | Out-Null
Test-RequiredPath "scripts\install-local-agent-task.ps1" "Autostart-Skript" | Out-Null

Write-Host ""
Write-Host "--- Tooling ---" -ForegroundColor Cyan

if (Test-CommandExists "node") {
    $nodeVersion = (& node --version)
    Write-Ok "Node verfügbar: $nodeVersion"
}
else {
    Write-ErrorStatus "Node.js ist nicht im PATH."
}

if (Test-CommandExists "npm") {
    $npmVersion = (& npm --version)
    Write-Ok "npm verfügbar: $npmVersion"
}
else {
    Write-ErrorStatus "npm ist nicht im PATH."
}

if (Test-CommandExists "py") {
    $pythonVersion = (& py -3 --version)
    Write-Ok "Python Launcher verfügbar: $pythonVersion"
}
else {
    Write-ErrorStatus "Python Launcher 'py' ist nicht im PATH."
}

Write-Host ""
Write-Host "--- Backend Konfiguration ---" -ForegroundColor Cyan

$backendEnvPath = Join-Path $RepoRoot "backend\.env"
$backendExamplePath = Join-Path $RepoRoot "backend\.env.example"

if (Test-Path $backendEnvPath) {
    Write-Ok "backend\.env vorhanden."
    $backendEnv = Read-EnvFile $backendEnvPath

    Test-SecretConfigured $backendEnv "OPENAI_API_KEY"
    Test-SecretConfigured $backendEnv "JARVIS_AGENT_TOKEN"
    Test-SecretConfigured $backendEnv "JARVIS_BOT_BRIDGE_TOKEN"
    Test-SecretConfigured $backendEnv "JARVIS_DASHBOARD_TOKEN"

    if ($backendEnv.ContainsKey("JARVIS_BACKEND_PORT")) {
        if ([string]$backendEnv["JARVIS_BACKEND_PORT"] -eq "8181") {
            Write-Ok "JARVIS_BACKEND_PORT ist 8181."
        }
        else {
            Write-Warn "JARVIS_BACKEND_PORT ist nicht 8181. Gewollter Projektstandard ist 8181."
        }
    }
    else {
        Write-Warn "JARVIS_BACKEND_PORT fehlt in backend\.env. Fallback aus Code kann greifen."
    }

    if ($backendEnv.ContainsKey("JARVIS_ALLOWED_DISCORD_USER_IDS")) {
        $value = [string]$backendEnv["JARVIS_ALLOWED_DISCORD_USER_IDS"]
        if (-not $value -or $value.ToUpperInvariant().Contains("CHANGE_ME")) {
            Write-ConfigRequired "JARVIS_ALLOWED_DISCORD_USER_IDS ist nicht produktiv gesetzt."
        }
        else {
            Write-Ok "JARVIS_ALLOWED_DISCORD_USER_IDS ist gesetzt."
        }
    }
    else {
        Write-ConfigRequired "JARVIS_ALLOWED_DISCORD_USER_IDS fehlt."
    }
}
else {
    Write-ConfigRequired "backend\.env fehlt. Kopiere backend\.env.example nach backend\.env und setze echte Werte."
    if (Test-Path $backendExamplePath) {
        Write-Ok "backend\.env.example vorhanden."
    }
    else {
        Write-ErrorStatus "backend\.env.example fehlt."
    }
}

Write-Host ""
Write-Host "--- Agent Konfiguration ---" -ForegroundColor Cyan

$agentConfigPath = Join-Path $RepoRoot "desktop-agent\config.json"
$agentLocalConfigPath = Join-Path $RepoRoot "desktop-agent\config.local.json"

$agentConfig = Read-JsonFile $agentConfigPath
if ($agentConfig) {
    Write-Ok "desktop-agent\config.json ist gültiges JSON."

    if ($agentConfig.backendUrl) {
        Write-Ok "Agent backendUrl ist im Basis-Config gesetzt."
    }
    else {
        Write-ConfigRequired "Agent backendUrl fehlt im Basis-Config."
    }

    if ($agentConfig.localApi -and $agentConfig.localApi.enabled -eq $true) {
        Write-Ok "Lokale Agent-API ist im Basis-Config aktiviert."
    }
    else {
        Write-Warn "Lokale Agent-API ist im Basis-Config nicht aktiviert."
    }

    if ($agentConfig.todo -and $agentConfig.todo.provider) {
        Write-Ok "TODO Provider im Basis-Config: $($agentConfig.todo.provider)"
    }
    else {
        Write-Warn "TODO Provider fehlt im Basis-Config."
    }

    if ($agentConfig.runtime -and $agentConfig.runtime.heartbeatIntervalSeconds) {
        Write-Ok "Agent Heartbeat-Intervall konfiguriert."
    }
    else {
        Write-Warn "Agent Heartbeat-Intervall fehlt."
    }
}

if (Test-Path $agentLocalConfigPath) {
    Write-Ok "desktop-agent\config.local.json vorhanden."
    $agentLocalConfig = Read-JsonFile $agentLocalConfigPath

    if ($agentLocalConfig) {
        Write-Ok "desktop-agent\config.local.json ist gültiges JSON."

        if ($agentLocalConfig.apps) {
            Write-Ok "Lokale App-Konfiguration vorhanden."
        }
        else {
            Write-Warn "config.local.json enthält keine apps-Overrides."
        }

        if ($agentLocalConfig.todo) {
            Write-Ok "Lokale TODO-Konfiguration vorhanden."
        }
        else {
            Write-Warn "config.local.json enthält keine todo-Overrides."
        }
    }
}
else {
    Write-ConfigRequired "desktop-agent\config.local.json fehlt. Lokale Pfade/Tokens müssen dort oder per ENV gesetzt werden."
}

Write-Host ""
Write-Host "--- Backend Build ---" -ForegroundColor Cyan

if ($SkipBackendBuild) {
    Write-Warn "Backend Build wurde übersprungen."
}
elseif ((Test-Path (Join-Path $RepoRoot "backend\package.json")) -and (Test-CommandExists "npm")) {
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        & npm run build
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Backend Build erfolgreich."
        }
        else {
            Write-ErrorStatus "Backend Build fehlgeschlagen. ExitCode=$LASTEXITCODE"
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
Write-Host "--- Agent Python Compile ---" -ForegroundColor Cyan

if ($SkipAgentCompile) {
    Write-Warn "Agent Python Compile wurde übersprungen."
}
elseif ((Test-Path (Join-Path $RepoRoot "desktop-agent\src")) -and (Test-CommandExists "py")) {
    $pyFiles = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "desktop-agent\src") -Recurse -Filter "*.py" |
        Where-Object { $_.FullName -notmatch "__pycache__" } |
        ForEach-Object { $_.FullName }

    if ($pyFiles.Count -eq 0) {
        Write-ErrorStatus "Keine Python-Dateien im Agent gefunden."
    }
    else {
        & py -3 -m py_compile @pyFiles
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Agent Python Compile erfolgreich."
        }
        else {
            Write-ErrorStatus "Agent Python Compile fehlgeschlagen. ExitCode=$LASTEXITCODE"
        }
    }
}
else {
    Write-ErrorStatus "Agent Compile nicht möglich: desktop-agent\src oder py fehlt."
}

Write-Host ""
Write-Host "--- Lokale Agent API ---" -ForegroundColor Cyan

if ($CheckLocalApi) {
    try {
        $health = Invoke-RestMethod $LocalApiUrl -TimeoutSec 5
        if ($health.ok -eq $true) {
            Write-Ok "Lokale Agent-API Health erreichbar: $LocalApiUrl"
            Write-Ok "Agent Runtime: $($health.runtime.status)"
            Write-Ok "TODO Provider: $($health.todo.provider)"
        }
        else {
            Write-Warn "Lokale Agent-API antwortet, aber ok ist nicht true."
        }
    }
    catch {
        Write-Warn "Lokale Agent-API nicht erreichbar: $LocalApiUrl | $($_.Exception.Message)"
    }
}
else {
    Write-Warn "Lokale Agent-API Healthcheck übersprungen. Nutze -CheckLocalApi zum Prüfen."
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
