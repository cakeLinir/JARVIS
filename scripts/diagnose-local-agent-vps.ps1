param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$BackendUrl = "",
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"

function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Fail([string]$Message) { Write-Err $Message; exit 2 }

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

$agentName = Get-ConfigValue $config @("agentName", "agent.name")
$agentToken = Get-ConfigValue $config @("agentToken", "backend.agentToken", "agent.token")

if (-not $BackendUrl.Trim()) {
    Fail "BackendUrl fehlt in config.local.json."
}

$base = $BackendUrl.Trim().TrimEnd("/")
$uri = [Uri]$base

Write-Host "=== JARVIS Local Agent VPS Diagnostics ===" -ForegroundColor Cyan
Write-Host "BackendUrl: $base"
Write-Host "Host:       $($uri.Host)"
Write-Host "Scheme:     $($uri.Scheme)"
Write-Host "AgentName:  $(if ($agentName) { $agentName } else { '<fehlt>' })"
Write-Host "Token:      $(if ($agentToken) { 'gesetzt' } else { '<fehlt>' })"
Write-Host ""

try {
    $dns = Resolve-DnsName -Name $uri.Host -ErrorAction Stop
    $addresses = $dns | Where-Object { $_.IPAddress } | Select-Object -ExpandProperty IPAddress -Unique
    Write-Ok "DNS-Auflösung erfolgreich: $($addresses -join ', ')"
}
catch {
    Write-Err "DNS-Auflösung fehlgeschlagen: $($_.Exception.Message)"
}

$port = if ($uri.Port -gt 0) { $uri.Port } elseif ($uri.Scheme -eq "https") { 443 } else { 80 }

try {
    $tcp = Test-NetConnection -ComputerName $uri.Host -Port $port -WarningAction SilentlyContinue
    if ($tcp.TcpTestSucceeded) {
        Write-Ok "TCP erreichbar: $($uri.Host):$port"
    }
    else {
        Write-Err "TCP nicht erreichbar: $($uri.Host):$port"
    }
}
catch {
    Write-Err "TCP-Test fehlgeschlagen: $($_.Exception.Message)"
}

try {
    $healthUrl = "$base/api/health"
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec $TimeoutSeconds
    Write-Ok "Health erreichbar: $healthUrl"
    $health | ConvertTo-Json -Depth 8
}
catch {
    Write-Err "Health nicht erreichbar: $base/api/health | $($_.Exception.Message)"
}

if ($agentToken) {
    try {
        $statusUrl = "$base/api/agent/status"
        $body = @{
            agentName = if ($agentName) { $agentName } else { "jarvis-desktop-agent" }
            hostname = $env:COMPUTERNAME
            status = "online"
            timestamp = (Get-Date).ToUniversalTime().ToString("o")
            source = "local-agent-diagnostics"
            capabilities = @("diagnostics")
        } | ConvertTo-Json -Depth 8

        $headers = @{
            Authorization = "Bearer $agentToken"
            "Content-Type" = "application/json"
        }

        $status = Invoke-RestMethod `
            -Uri $statusUrl `
            -Method Post `
            -Headers $headers `
            -Body $body `
            -TimeoutSec $TimeoutSeconds

        Write-Ok "Agent Status POST erfolgreich: $statusUrl"
        $status | ConvertTo-Json -Depth 8
    }
    catch {
        Write-Err "Agent Status POST fehlgeschlagen: $base/api/agent/status | $($_.Exception.Message)"
    }
}
else {
    Write-Warn "AgentToken fehlt; Agent Status POST übersprungen."
}

Write-Host ""
Write-Host "Hinweis:" -ForegroundColor Cyan
Write-Host "Wenn Health OK ist, aber Agent POST fehlschlägt, ist meistens der Agent Token falsch."
Write-Host "Wenn bereits DNS/TCP/Health fehlschlagen, ist es Netzwerk/Caddy/Firewall/DNS."
