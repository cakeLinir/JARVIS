param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$BackendUrl = "",
    [string]$AgentName = "",
    [string]$AgentToken = "",
    [int]$TimeoutSeconds = 10
)

$ErrorActionPreference = "Stop"

function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

function Get-ConfigValue([object]$Config, [string[]]$Paths) {
    foreach ($path in $Paths) {
        $current = $Config
        $ok = $true

        foreach ($part in $path.Split(".")) {
            if ($null -eq $current -or -not $current.PSObject.Properties[$part]) {
                $ok = $false
                break
            }

            $current = $current.$part
        }

        if ($ok -and $null -ne $current -and "$current".Trim()) {
            return "$current"
        }
    }

    return ""
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$configPath = Join-Path $repoRootResolved "desktop-agent\config.local.json"

if (-not (Test-Path $configPath)) {
    Fail "desktop-agent\config.local.json nicht gefunden: $configPath"
}

$config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json

if (-not $BackendUrl.Trim()) {
    $BackendUrl = Get-ConfigValue $config @("backendUrl", "backend.url")
}

if (-not $AgentName.Trim()) {
    $AgentName = Get-ConfigValue $config @("agentName", "agent.name")
}

if (-not $AgentToken.Trim()) {
    $AgentToken = Get-ConfigValue $config @("agentToken", "backend.agentToken", "agent.token")
}

if (-not $BackendUrl.Trim()) {
    Fail "BackendUrl fehlt in config.local.json."
}

if (-not $AgentName.Trim()) {
    $AgentName = "jarvis-desktop-agent"
    Write-Warn "AgentName fehlt; nutze Standard: $AgentName"
}

if (-not $AgentToken.Trim()) {
    Fail "AgentToken fehlt. Setze ihn über configure-local-agent-vps.ps1 oder config.local.json."
}

$base = $BackendUrl.Trim().TrimEnd("/")
$statusUrl = "$base/api/agent/status"

$body = @{
    agentName = $AgentName
    hostname = $env:COMPUTERNAME
    status = "online"
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    source = "manual-vps-connectivity-test"
    capabilities = @("status-test")
} | ConvertTo-Json -Depth 8

$headers = @{
    Authorization = "Bearer $AgentToken"
    "Content-Type" = "application/json"
}

Write-Host "=== JARVIS Local Agent VPS Connection Test ===" -ForegroundColor Cyan
Write-Host "Backend: $base"
Write-Host "Endpoint: $statusUrl"
Write-Host "Agent:   $AgentName"

try {
    $response = Invoke-RestMethod `
        -Uri $statusUrl `
        -Method Post `
        -Headers $headers `
        -Body $body `
        -TimeoutSec $TimeoutSeconds

    Write-Ok "Agent-Status erfolgreich an VPS gesendet."
    $response | ConvertTo-Json -Depth 8
    exit 0
}
catch {
    Write-Host ""
    Write-Host "[ERROR] Agent-Status konnte nicht gesendet werden." -ForegroundColor Red
    Write-Host $_.Exception.Message

    if ($_.Exception.Response) {
        try {
            $statusCode = $_.Exception.Response.StatusCode.value__
            Write-Host "HTTP Status: $statusCode"
        }
        catch {}
    }

    exit 2
}
