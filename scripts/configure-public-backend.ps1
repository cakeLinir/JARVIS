param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$PublicHost = "46.225.14.84",
    [int]$Port = 8181,
    [switch]$AllowInsecurePublicHttp
)

$ErrorActionPreference = "Stop"

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

if (-not $AllowInsecurePublicHttp) {
    Fail "SICHERHEITSRISIKO: Direkter HTTP-Zugriff über öffentliche IP ist blockiert. Nutze bewusst -AllowInsecurePublicHttp oder verwende .\scripts\configure-https-backend.ps1."
}

$envPath = Join-Path $RepoRoot "backend\.env"

if (-not (Test-Path $envPath)) {
    Fail "backend\.env nicht gefunden: $envPath"
}

$content = Get-Content -LiteralPath $envPath -Encoding UTF8 -Raw

function Set-EnvValue([string]$Key, [string]$Value) {
    $script:content = $script:content -replace "(?m)^$([regex]::Escape($Key))=.*$", "$Key=$Value"

    if ($script:content -notmatch "(?m)^$([regex]::Escape($Key))=") {
        if (-not $script:content.EndsWith("`n")) {
            $script:content += "`n"
        }
        $script:content += "$Key=$Value`n"
    }
}

$publicBaseUrl = "http://${PublicHost}:$Port"

Set-EnvValue "JARVIS_BACKEND_HOST" "0.0.0.0"
Set-EnvValue "JARVIS_BACKEND_PORT" "$Port"
Set-EnvValue "JARVIS_PUBLIC_HOST" "$PublicHost"
Set-EnvValue "JARVIS_PUBLIC_BASE_URL" "$publicBaseUrl"
Set-EnvValue "JARVIS_DISCORD_OAUTH_REDIRECT_URI" "$publicBaseUrl/dashboard/auth/discord/callback"
Set-EnvValue "JARVIS_DASHBOARD_COOKIE_SECURE" "false"

Set-Content -LiteralPath $envPath -Value $content -Encoding UTF8

Write-Ok "Backend Public-Konfiguration gesetzt."
Write-Host "Bind Host:       0.0.0.0"
Write-Host "Port:            $Port"
Write-Host "Public Base URL: $publicBaseUrl"
Write-Host "Dashboard:       $publicBaseUrl/dashboard"
Write-Warn "SICHERHEITSRISIKO: Direkter HTTP-Zugriff über öffentliche IP ist nur für Testbetrieb empfohlen. Produktiv HTTPS/Reverse Proxy nutzen."
