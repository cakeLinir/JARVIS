param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$TodoPath = "",
    [string]$ReviewOut = "",
    [string]$ScheduleOut = "",
    [string]$ApplyLogOut = "",
    [switch]$ApplyToTodo
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$reviewModule = Join-Path $repoRootResolved "desktop-agent\src\todo\todo_review.py"

if (-not (Test-Path $reviewModule)) {
    Fail "todo_review.py nicht gefunden: $reviewModule"
}

if (-not $TodoPath.Trim()) {
    $TodoPath = Join-Path $repoRootResolved "data\todo.md"
}

if (-not $ReviewOut.Trim()) {
    $ReviewOut = Join-Path $repoRootResolved "data\todo.review.json"
}

if (-not $ScheduleOut.Trim()) {
    $ScheduleOut = Join-Path $repoRootResolved "data\todo.schedule.json"
}

if (-not $ApplyLogOut.Trim()) {
    $ApplyLogOut = Join-Path $repoRootResolved "data\todo.apply-log.json"
}

if (-not (Test-Path $TodoPath)) {
    Fail "TODO-Datei nicht gefunden: $TodoPath"
}

Write-Host "[INFO] Python Compile..." -ForegroundColor Cyan
py -3 -m py_compile $reviewModule

if ($LASTEXITCODE -ne 0) {
    Fail "py_compile fehlgeschlagen."
}

Write-Host "[INFO] Erzeuge TODO Review und Schedule..." -ForegroundColor Cyan

$argsList = @(
    $reviewModule,
    "--todo", $TodoPath,
    "--review-out", $ReviewOut,
    "--schedule-out", $ScheduleOut
)

if ($ApplyToTodo) {
    $backupDir = Join-Path (Split-Path $TodoPath -Parent) "backups"
    $argsList += @(
        "--apply",
        "--backup-dir", $backupDir,
        "--apply-log-out", $ApplyLogOut
    )
}

py -3 @argsList

if ($LASTEXITCODE -ne 0) {
    Fail "TODO Review Generator fehlgeschlagen."
}

if (-not (Test-Path $ReviewOut)) {
    Fail "Review-Datei wurde nicht erstellt: $ReviewOut"
}

if (-not (Test-Path $ScheduleOut)) {
    Fail "Schedule-Datei wurde nicht erstellt: $ScheduleOut"
}

$review = Get-Content -LiteralPath $ReviewOut -Raw | ConvertFrom-Json
$schedule = Get-Content -LiteralPath $ScheduleOut -Raw | ConvertFrom-Json

if ($review.kind -ne "jarvis.todo.review") {
    Fail "Review-Datei hat unerwarteten kind-Wert: $($review.kind)"
}

if ($schedule.kind -ne "jarvis.todo.schedule") {
    Fail "Schedule-Datei hat unerwarteten kind-Wert: $($schedule.kind)"
}

if ($review.policy.applyAllowed -ne $true) {
    Fail "Review applyAllowed muss true sein."
}

if ($review.policy.applyRequiresBackup -ne $true) {
    Fail "Review applyRequiresBackup muss true sein."
}

if ($schedule.policy.autoStart -ne $false) {
    Fail "Schedule autoStart muss false sein."
}

if ($ApplyToTodo) {
    if (-not (Test-Path $ApplyLogOut)) {
        Fail "Apply-Log wurde nicht erstellt: $ApplyLogOut"
    }

    $applyLog = Get-Content -LiteralPath $ApplyLogOut -Raw | ConvertFrom-Json

    if (-not (Test-Path $applyLog.backupPath)) {
        Fail "Backup-Datei aus Apply-Log nicht gefunden: $($applyLog.backupPath)"
    }
}

Write-Host "[OK] TODO Review Test erfolgreich." -ForegroundColor Green
Write-Host "Review:   $ReviewOut"
Write-Host "Schedule: $ScheduleOut"

if ($ApplyToTodo) {
    Write-Host "ApplyLog: $ApplyLogOut"
}
