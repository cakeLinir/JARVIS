param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$Domain = "jarvis.hundekuchenlive.de",
    [int]$Port = 8181,
    [string]$RedirectPath = "/dashboard/auth/discord/callback"
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

$publicBaseUrl = "https://$Domain"
$redirectUri = "$publicBaseUrl$RedirectPath"

Set-EnvValue "JARVIS_BACKEND_HOST" "127.0.0.1"
Set-EnvValue "JARVIS_BACKEND_PORT" "$Port"
Set-EnvValue "JARVIS_PUBLIC_HOST" "$Domain"
Set-EnvValue "JARVIS_PUBLIC_BASE_URL" "$publicBaseUrl"
Set-EnvValue "JARVIS_DISCORD_OAUTH_REDIRECT_URI" "$redirectUri"
Set-EnvValue "JARVIS_DASHBOARD_COOKIE_SECURE" "true"
Set-EnvValue "JARVIS_DASHBOARD_SESSION_IDLE_SECONDS" "1800"
Set-EnvValue "JARVIS_DASHBOARD_SESSION_TTL_SECONDS" "1800"

Set-Content -LiteralPath $envPath -Value $content -Encoding UTF8

Write-Ok "Backend HTTPS/Caddy-Konfiguration gesetzt."
Write-Host "Bind Host:       127.0.0.1"
Write-Host "Port:            $Port"
Write-Host "Public Base URL: $publicBaseUrl"
Write-Host "Dashboard:       $publicBaseUrl/dashboard"
Write-Host "Redirect URI:    $redirectUri"
Write-Host ""
Write-Warn "Backend neu starten, damit .env neu geladen wird."
