param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [switch]$ApplyToTodo
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$commandModule = Join-Path $repoRootResolved "desktop-agent\src\todo\todo_review_command.py"
$reviewModule = Join-Path $repoRootResolved "desktop-agent\src\todo\todo_review.py"

if (-not (Test-Path $commandModule)) {
    Fail "todo_review_command.py nicht gefunden: $commandModule"
}

if (-not (Test-Path $reviewModule)) {
    Fail "todo_review.py nicht gefunden: $reviewModule"
}

Write-Host "[INFO] Python Compile..." -ForegroundColor Cyan
py -3 -m py_compile $reviewModule $commandModule

if ($LASTEXITCODE -ne 0) {
    Fail "py_compile fehlgeschlagen."
}

Write-Host "[INFO] Agent TODO Review Command Smoke-Test..." -ForegroundColor Cyan

$argsList = @(
    $commandModule,
    "--repo-root", $repoRootResolved
)

if ($ApplyToTodo) {
    $argsList += "--apply"
}

py -3 @argsList

if ($LASTEXITCODE -ne 0) {
    Fail "Agent TODO Review Command fehlgeschlagen."
}

$reviewOut = Join-Path $repoRootResolved "data\todo.review.json"
$scheduleOut = Join-Path $repoRootResolved "data\todo.schedule.json"
$applyLogOut = Join-Path $repoRootResolved "data\todo.apply-log.json"

if (-not (Test-Path $reviewOut)) {
    Fail "Review-Datei fehlt: $reviewOut"
}

if (-not (Test-Path $scheduleOut)) {
    Fail "Schedule-Datei fehlt: $scheduleOut"
}

$review = Get-Content -LiteralPath $reviewOut -Raw | ConvertFrom-Json
$schedule = Get-Content -LiteralPath $scheduleOut -Raw | ConvertFrom-Json

if ($review.kind -ne "jarvis.todo.review") {
    Fail "Review kind unerwartet: $($review.kind)"
}

if ($schedule.kind -ne "jarvis.todo.schedule") {
    Fail "Schedule kind unerwartet: $($schedule.kind)"
}

if ($ApplyToTodo) {
    if (-not (Test-Path $applyLogOut)) {
        Fail "Apply-Log fehlt: $applyLogOut"
    }

    $applyLog = Get-Content -LiteralPath $applyLogOut -Raw | ConvertFrom-Json

    if (-not (Test-Path $applyLog.backupPath)) {
        Fail "Backup aus Apply-Log fehlt: $($applyLog.backupPath)"
    }
}

Write-Host "[OK] Agent TODO Review Command Test erfolgreich." -ForegroundColor Green
