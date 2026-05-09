param(
    [string]$CaddyDir = "C:\caddy",
    [string]$Domain = "jarvis.hundekuchenlive.de",
    [string]$Upstream = "127.0.0.1:8181",
    [string]$Email = "",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

$caddyExe = Join-Path $CaddyDir "caddy.exe"
$caddyFile = Join-Path $CaddyDir "Caddyfile"

if (-not (Test-Path $CaddyDir)) { Fail "Caddy-Verzeichnis nicht gefunden: $CaddyDir" }

if (-not (Test-Path $caddyExe)) {
    $pathCaddy = Get-Command caddy -ErrorAction SilentlyContinue
    if ($pathCaddy) {
        $caddyExe = $pathCaddy.Source
        Write-Warn "C:\caddy\caddy.exe nicht gefunden. Nutze caddy aus PATH: $caddyExe"
    } else {
        Fail "caddy.exe nicht gefunden: $caddyExe"
    }
}

$globalBlock = ""
if ($Email.Trim()) {
    $globalBlock = @"
{
	email $Email
}

"@
}

$caddyContent = @"
$globalBlock# JARVIS reverse proxy
# Managed by scripts/caddy-install-jarvis-config.ps1

$Domain {
	encode zstd gzip

	header {
		X-Content-Type-Options "nosniff"
		Referrer-Policy "no-referrer"
		X-Frame-Options "DENY"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
	}

	reverse_proxy $Upstream
}
"@

if (Test-Path $caddyFile) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $CaddyDir "Caddyfile.backup-$timestamp"
    Copy-Item -LiteralPath $caddyFile -Destination $backup -Force
    Write-Ok "Bestehende Caddyfile gesichert: $backup"
}

Set-Content -LiteralPath $caddyFile -Value $caddyContent -Encoding UTF8
Write-Ok "Caddyfile geschrieben: $caddyFile"

Write-Info "Validiere Caddyfile..."
& $caddyExe validate --config $caddyFile
if ($LASTEXITCODE -ne 0) { Fail "Caddyfile-Validierung fehlgeschlagen." }
Write-Ok "Caddyfile ist gültig."

if ($Reload) {
    Write-Info "Lade Caddy-Konfiguration neu..."
    & $caddyExe reload --config $caddyFile
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Caddy reload fehlgeschlagen. Falls Caddy nicht läuft, starte ihn manuell oder als Service."
        exit 1
    }
    Write-Ok "Caddy reload erfolgreich."
} else {
    Write-Warn "Reload wurde nicht ausgeführt. Nutze -Reload oder starte Caddy manuell neu."
}

Write-Host ""
Write-Host "Erwartete öffentliche URL:" -ForegroundColor Cyan
Write-Host "https://$Domain/dashboard"
Write-Host ""
Write-Host "Backend sollte lokal laufen auf:" -ForegroundColor Cyan
Write-Host "http://$Upstream"
