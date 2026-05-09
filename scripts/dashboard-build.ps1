param(
    [string]$RepoRoot = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$dashboardDir = Join-Path $RepoRoot "dashboard"

if (-not (Test-Path (Join-Path $dashboardDir "package.json"))) {
    Write-Host "[ERROR] dashboard\package.json nicht gefunden." -ForegroundColor Red
    exit 2
}

Push-Location $dashboardDir
try {
    npm install
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    npm run build
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
