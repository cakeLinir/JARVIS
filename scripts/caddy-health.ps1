param(
    [string]$PublicUrl = "https://jarvis.hundekuchenlive.de",
    [string]$LocalBackendUrl = "http://127.0.0.1:8181/api/health",
    [int]$TimeoutSeconds = 8
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

Write-Host "=== JARVIS Caddy HTTPS Health ===" -ForegroundColor Cyan

try {
    Invoke-RestMethod -Uri $LocalBackendUrl -TimeoutSec $TimeoutSeconds | Out-Null
    Write-Ok "Lokales Backend erreichbar: $LocalBackendUrl"
}
catch {
    Write-ErrorStatus "Lokales Backend nicht erreichbar: $LocalBackendUrl | $($_.Exception.Message)"
}

try {
    $publicHealthUrl = "$PublicUrl/api/health"
    Invoke-RestMethod -Uri $publicHealthUrl -TimeoutSec $TimeoutSeconds | Out-Null
    Write-Ok "Öffentlicher HTTPS-Healthcheck erreichbar: $publicHealthUrl"
}
catch {
    Write-ErrorStatus "Öffentlicher HTTPS-Healthcheck nicht erreichbar: $PublicUrl/api/health | $($_.Exception.Message)"
}

try {
    $dashboardUrl = "$PublicUrl/dashboard"
    $response = Invoke-WebRequest -Uri $dashboardUrl -TimeoutSec $TimeoutSeconds -MaximumRedirection 0 -UseBasicParsing -ErrorAction Stop

    if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
        if ($response.Content -match "JARVIS Dashboard" -or $response.Content -match "root") {
            Write-Ok "Dashboard Frontend erreichbar: $dashboardUrl"
        }
        else {
            Write-Warn "Dashboard antwortet, aber Inhalt sieht nicht eindeutig nach Frontend aus: $dashboardUrl"
        }
    }
    else {
        Write-Warn "Dashboard antwortet mit HTTP $($response.StatusCode): $dashboardUrl"
    }
}
catch {
    Write-Warn "Dashboard Frontend Test unklar: $($_.Exception.Message)"
}

try {
    $oauthUrl = "$PublicUrl/dashboard/auth/discord/start"
    $response = Invoke-WebRequest -Uri $oauthUrl -TimeoutSec $TimeoutSeconds -MaximumRedirection 0 -UseBasicParsing -ErrorAction SilentlyContinue

    if ($response.StatusCode -in @(302, 303, 307, 308)) {
        Write-Ok "Discord OAuth Start wird vom Backend beantwortet: $oauthUrl"
    }
    elseif ($response.Headers.Location) {
        Write-Ok "Discord OAuth Start liefert Redirect: $($response.Headers.Location)"
    }
    else {
        Write-Warn "Discord OAuth Start antwortet nicht eindeutig mit Redirect. HTTP $($response.StatusCode)"
    }
}
catch {
    $status = $_.Exception.Response.StatusCode.value__
    if ($status -in @(302, 303, 307, 308)) {
        Write-Ok "Discord OAuth Start liefert Redirect."
    }
    else {
        Write-Warn "Discord OAuth Start Test unklar: $($_.Exception.Message)"
    }
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
