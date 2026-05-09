param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [int]$KeepDays = 14,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

$targets = @(
    (Join-Path $RepoRoot "logs\backend"),
    (Join-Path $RepoRoot "logs\backend-watchdog"),
    (Join-Path $RepoRoot "backend\data")
)

$cutoff = (Get-Date).AddDays(-$KeepDays)
$deleted = 0
$matched = 0

Write-Host "=== JARVIS Log Cleanup ===" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot"
Write-Host "KeepDays: $KeepDays"
Write-Host "Cutoff:   $cutoff"

foreach ($target in $targets) {
    if (-not (Test-Path $target)) {
        continue
    }

    $files = Get-ChildItem -LiteralPath $target -Recurse -File |
        Where-Object {
            $_.LastWriteTime -lt $cutoff -and
            (
                $_.Extension -in @(".log", ".jsonl", ".txt") -or
                $_.Name -match "\.err\.log$" -or
                $_.Name -match "\.out\.log$"
            )
        }

    foreach ($file in $files) {
        $matched += 1

        if ($WhatIfOnly) {
            Write-Host "[WHATIF] $($file.FullName)"
            continue
        }

        Remove-Item -LiteralPath $file.FullName -Force
        $deleted += 1
        Write-Host "[OK] gelöscht: $($file.FullName)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Matched: $matched"
Write-Host "Deleted: $deleted"

exit 0
