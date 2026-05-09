param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [switch]$ReloadCaddy
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 2 }

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$buildScript = Join-Path $repoRootResolved "scripts\dashboard-build.ps1"
$caddyScript = Join-Path $repoRootResolved "scripts\caddy-install-jarvis-config.ps1"

if (-not (Test-Path $buildScript)) {
    Fail "dashboard-build.ps1 nicht gefunden: $buildScript"
}

if (-not (Test-Path $caddyScript)) {
    Fail "caddy-install-jarvis-config.ps1 nicht gefunden: $caddyScript"
}

Write-Info "Baue Dashboard..."
& $buildScript -RepoRoot $repoRootResolved

if ($LASTEXITCODE -ne 0) {
    Fail "Dashboard Build fehlgeschlagen. ExitCode=$LASTEXITCODE"
}

Write-Ok "Dashboard Build erfolgreich."

if ($ReloadCaddy) {
    Write-Info "Aktualisiere Caddy-Konfiguration und lade neu..."
    & $caddyScript -RepoRoot $repoRootResolved -Reload

    if ($LASTEXITCODE -ne 0) {
        Fail "Caddy Reload fehlgeschlagen. ExitCode=$LASTEXITCODE"
    }

    Write-Ok "Caddy Reload erfolgreich."
}
else {
    Write-Info "Caddy Reload übersprungen. Nutze -ReloadCaddy zum direkten Neuladen."
}
