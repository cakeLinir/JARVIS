param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$PublicIp = "46.225.14.84",
    [int]$Port = 8181,
    [string]$BindHost = "0.0.0.0",
    [string]$Protocol = "http"
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

$backendDir = Join-Path $RepoRoot "backend"
$envPath = Join-Path $backendDir ".env"
$examplePath = Join-Path $backendDir ".env.example"

if (-not (Test-Path $backendDir)) {
    throw "Backend-Ordner nicht gefunden: $backendDir"
}

if (-not (Test-Path $envPath)) {
    if (-not (Test-Path $examplePath)) {
        throw "backend\.env fehlt und backend\.env.example wurde nicht gefunden."
    }

    Copy-Item -LiteralPath $examplePath -Destination $envPath -Force
    Write-Warn "backend\.env wurde aus backend\.env.example erstellt. Secrets müssen manuell gesetzt werden."
}

function Set-EnvKey([string]$Path, [string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    }

    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))=") {
            $found = $true
            "$Key=$Value"
        }
        else {
            $line
        }
    }

    if (-not $found) {
        $updated += "$Key=$Value"
    }

    Set-Content -LiteralPath $Path -Value $updated -Encoding UTF8
}

$publicBaseUrl = "$Protocol`://$PublicIp`:$Port"

Set-EnvKey $envPath "JARVIS_BACKEND_HOST" $BindHost
Set-EnvKey $envPath "JARVIS_BACKEND_PORT" ([string]$Port)
Set-EnvKey $envPath "JARVIS_BACKEND_PUBLIC_HOST" $PublicIp
Set-EnvKey $envPath "JARVIS_BACKEND_PUBLIC_PROTOCOL" $Protocol
Set-EnvKey $envPath "JARVIS_PUBLIC_BASE_URL" $publicBaseUrl

Write-Ok "Backend Public-Konfiguration gesetzt."
Write-Host "Bind Host:       $BindHost"
Write-Host "Port:            $Port"
Write-Host "Public Base URL: $publicBaseUrl"
Write-Host "Dashboard:       $publicBaseUrl/dashboard"

Write-Warn "SICHERHEITSRISIKO: Direkter HTTP-Zugriff über öffentliche IP ist nur für Testbetrieb empfohlen. Produktiv HTTPS/Reverse Proxy nutzen."
