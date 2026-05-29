<#
.SYNOPSIS JARVIS Konfiguration – https | public | vps-sparse
(configure-local-agent-vps wurde in agent.ps1 -Action config integriert)
#>
param(
  [Parameter(Position = 0)] [ValidateSet("https","public","vps-sparse")] [string]$Action,
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$Domain = "jarvis.hundekuchenlive.de",
  [int] $Port = 8181,
  [string]$PublicHost = "46.225.14.84",
  [switch]$AllowInsecurePublicHttp,
  [switch]$ApplyPull
)
$ErrorActionPreference = "Stop"
$RepoRootResolved = (Resolve-Path $RepoRoot).Path
$EnvPath = Join-Path $RepoRootResolved "backend\.env"

function Write-Ok([string]$m) { Write-Host "[OK] $m"    -ForegroundColor Green }
function Write-Warn([string]$m) { Write-Host "[WARN] $m"  -ForegroundColor Yellow }
function Fail([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 2 }

function Set-EnvValue([string]$Key, [string]$Value) {
  $script:content = $script:content -replace "(?m)^$([regex]::Escape($Key))=.*$", "$Key=$Value"
  if ($script:content -notmatch "(?m)^$([regex]::Escape($Key))=") {
    if (-not $script:content.EndsWith("`n")) { $script:content += "`n" }
    $script:content += "$Key=$Value`n"
  }
}

function Set-HttpsConfig {
  if (-not (Test-Path $EnvPath)) { Fail "backend\.env nicht gefunden." }
  $script:content = Get-Content -LiteralPath $EnvPath -Encoding UTF8 -Raw
  $publicBaseUrl = "https://$Domain"
  $redirectUri = "$publicBaseUrl/dashboard/auth/discord/callback"
  Set-EnvValue "JARVIS_BACKEND_HOST"                  "127.0.0.1"
  Set-EnvValue "JARVIS_BACKEND_PORT"                  "$Port"
  Set-EnvValue "JARVIS_PUBLIC_HOST"                   $Domain
  Set-EnvValue "JARVIS_PUBLIC_BASE_URL"               $publicBaseUrl
  Set-EnvValue "JARVIS_DISCORD_OAUTH_REDIRECT_URI"    $redirectUri
  Set-EnvValue "JARVIS_DASHBOARD_COOKIE_SECURE"       "true"
  Set-EnvValue "JARVIS_DASHBOARD_SESSION_IDLE_SECONDS" "1800"
  Set-EnvValue "JARVIS_DASHBOARD_SESSION_TTL_SECONDS"  "1800"
  Set-Content -LiteralPath $EnvPath -Value $script:content -Encoding UTF8
  Write-Ok "HTTPS-Konfiguration gesetzt. Public URL: $publicBaseUrl"
  Write-Warn "Backend neu starten: .\scripts\04_backend.ps1 -Action restart"
}

function Set-PublicConfig {
  if (-not $AllowInsecurePublicHttp) {
    Fail "SICHERHEITSRISIKO: Nutze bewusst -AllowInsecurePublicHttp oder verwende -Action https."
  }
  if (-not (Test-Path $EnvPath)) { Fail "backend\.env nicht gefunden." }
  $script:content = Get-Content -LiteralPath $EnvPath -Encoding UTF8 -Raw
  $publicBaseUrl = "http://${PublicHost}:$Port"
  Set-EnvValue "JARVIS_BACKEND_HOST"               "0.0.0.0"
  Set-EnvValue "JARVIS_BACKEND_PORT"               "$Port"
  Set-EnvValue "JARVIS_PUBLIC_HOST"                $PublicHost
  Set-EnvValue "JARVIS_PUBLIC_BASE_URL"            $publicBaseUrl
  Set-EnvValue "JARVIS_DISCORD_OAUTH_REDIRECT_URI" "$publicBaseUrl/dashboard/auth/discord/callback"
  Set-EnvValue "JARVIS_DASHBOARD_COOKIE_SECURE"    "false"
  Set-Content -LiteralPath $EnvPath -Value $script:content -Encoding UTF8
  Write-Ok "Public-HTTP-Konfiguration gesetzt. URL: $publicBaseUrl"
  Write-Warn "NUR für Testbetrieb! Produktiv HTTPS/Reverse-Proxy nutzen."
}

function Set-VpsSparseCheckout {
  Push-Location $RepoRootResolved
  try {
    $check = & git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0 -or $check.Trim() -ne "true") { Fail "Kein Git-Arbeitsbaum: $RepoRootResolved" }
    $status = & git status --porcelain
    if ($status) { Write-Warn "Working tree nicht sauber:`n$status" }
    & git sparse-checkout init --cone
    if ($LASTEXITCODE -ne 0) { Fail "sparse-checkout init fehlgeschlagen." }
    & git sparse-checkout set backend dashboard deploy docs scripts
    if ($LASTEXITCODE -ne 0) { Fail "sparse-checkout set fehlgeschlagen." }
    Write-Ok "Sparse-Checkout konfiguriert (backend, dashboard, deploy, docs, scripts)."
    if ($ApplyPull) {
      & git pull --ff-only
      if ($LASTEXITCODE -ne 0) { Fail "git pull fehlgeschlagen." }
      Write-Ok "git pull erfolgreich."
    }
  } finally { Pop-Location }
}

if (-not $Action) { Write-Host "Nutzung: config.ps1 -Action <https|public|vps-sparse>" -ForegroundColor Cyan; exit 0 }
switch ($Action) {
  "https"      { Set-HttpsConfig }
  "public"     { Set-PublicConfig }
  "vps-sparse" { Set-VpsSparseCheckout }
}
