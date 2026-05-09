param(
    [string]$RepoRoot = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$dashboardPackage = Join-Path $RepoRoot "dashboard\package.json"
$dashboardDist = Join-Path $RepoRoot "dashboard\dist\index.html"

Write-Host "=== JARVIS Dashboard Source Check ===" -ForegroundColor Cyan

if (Test-Path $dashboardPackage) {
    Write-Host "[OK] dashboard\package.json vorhanden." -ForegroundColor Green
}
else {
    Write-Host "[ERROR] dashboard\package.json fehlt." -ForegroundColor Red
    Write-Host ""
    Write-Host "Ursache:" -ForegroundColor Yellow
    Write-Host "  Patch 018 wurde auf diesem Repo-Stand nicht angewendet oder nicht auf den VPS gepullt."
    Write-Host ""
    Write-Host "Lösung:" -ForegroundColor Cyan
    Write-Host "  1. Lokal Patch 018 committen/pushen und auf dem VPS git pull ausführen."
    Write-Host "  2. Oder Patch 018 direkt im VPS-Repo C:\Bots\JARVIS anwenden."
    exit 2
}

if (Test-Path $dashboardDist) {
    Write-Host "[OK] dashboard\dist\index.html vorhanden." -ForegroundColor Green
}
else {
    Write-Host "[WARN] dashboard\dist\index.html fehlt. Führe .\scripts\dashboard-build.ps1 aus." -ForegroundColor Yellow
    exit 1
}

exit 0
