param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$BackendUrl = "https://jarvis.hundekuchenlive.de",
    [string]$AgentName = "jarvis-desktop-agent",
    [string]$AgentToken = "",
    [switch]$ReadTokenFromBackendEnv
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

function Get-EnvValueFromFile([string]$Path, [string]$Key) {
    if (-not (Test-Path $Path)) {
        return ""
    }

    $line = Get-Content -LiteralPath $Path -Encoding UTF8 |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } |
        Select-Object -First 1

    if (-not $line) {
        return ""
    }

    return ($line -replace "^\s*$([regex]::Escape($Key))\s*=\s*", "").Trim().Trim('"').Trim("'")
}

function Set-Property([object]$Object, [string]$Name, [object]$Value) {
    $property = $Object.PSObject.Properties[$Name]

    if ($property) {
        $Object.$Name = $Value
        return
    }

    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$configPath = Join-Path $repoRootResolved "desktop-agent\config.local.json"

if (-not (Test-Path $configPath)) {
    Fail "desktop-agent\config.local.json nicht gefunden: $configPath"
}

if (-not $AgentToken.Trim() -and $ReadTokenFromBackendEnv) {
    $envPath = Join-Path $repoRootResolved "backend\.env"
    $AgentToken = Get-EnvValueFromFile -Path $envPath -Key "JARVIS_AGENT_TOKEN"

    if ($AgentToken.Trim()) {
        Write-Ok "Agent Token aus backend\.env gelesen. Wert wird nicht ausgegeben."
    }
}

if (-not $AgentToken.Trim()) {
    Write-Warn "AgentToken wurde nicht angegeben. Bestehender Token in config.local.json bleibt erhalten, falls vorhanden."
}

$configRaw = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw
$config = $configRaw | ConvertFrom-Json

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = "$configPath.backup-$timestamp"
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
Write-Ok "Backup erstellt: $backupPath"

Set-Property -Object $config -Name "backendUrl" -Value $BackendUrl
Set-Property -Object $config -Name "agentName" -Value $AgentName

if ($AgentToken.Trim()) {
    Set-Property -Object $config -Name "agentToken" -Value $AgentToken
}

# Zusätzliche Kompatibilität für mögliche verschachtelte Konfiguration.
if ($config.PSObject.Properties["backend"] -and $null -ne $config.backend) {
    Set-Property -Object $config.backend -Name "url" -Value $BackendUrl

    if ($AgentToken.Trim()) {
        Set-Property -Object $config.backend -Name "agentToken" -Value $AgentToken
    }
}

if ($config.PSObject.Properties["agent"] -and $null -ne $config.agent) {
    Set-Property -Object $config.agent -Name "name" -Value $AgentName

    if ($AgentToken.Trim()) {
        Set-Property -Object $config.agent -Name "token" -Value $AgentToken
    }
}

$config |
    ConvertTo-Json -Depth 20 |
    Set-Content -LiteralPath $configPath -Encoding UTF8

Write-Ok "Lokale Agent-Konfiguration aktualisiert."
Write-Host "Backend URL: $BackendUrl"
Write-Host "Agent Name:  $AgentName"
Write-Host "Agent Token: $(if ($AgentToken.Trim()) { 'neu gesetzt' } else { 'bestehender Wert beibehalten' })"
Write-Host ""
Write-Host "Nächster Test:" -ForegroundColor Cyan
Write-Host "  .\scripts\test-local-agent-vps-connection.ps1"
Write-Host ""
Write-Host "Agent starten:" -ForegroundColor Cyan
Write-Host "  .\scripts\run-local-agent.ps1"
