param(
    [string]$RepoRoot = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$mainPath = Join-Path $repoRootResolved "desktop-agent\src\main.py"
$commandPath = Join-Path $repoRootResolved "desktop-agent\src\todo\todo_review_command.py"
$configPath = Join-Path $repoRootResolved "desktop-agent\config.json"

if (-not (Test-Path $mainPath)) {
    Fail "main.py nicht gefunden: $mainPath"
}

if (-not (Test-Path $commandPath)) {
    Fail "todo_review_command.py nicht gefunden: $commandPath"
}

Write-Host "[INFO] Python Compile..." -ForegroundColor Cyan
py -3 -m py_compile $mainPath $commandPath

if ($LASTEXITCODE -ne 0) {
    Fail "py_compile fehlgeschlagen."
}

Write-Host "[INFO] Prüfe Integration Marker..." -ForegroundColor Cyan
$mainText = Get-Content -LiteralPath $mainPath -Raw

if ($mainText -notmatch "JARVIS_PATCH_027_3_4") {
    Fail "Integration Marker JARVIS_PATCH_027_3_4 fehlt in main.py."
}

if ($mainText -notmatch "run_todo_review_for_morning") {
    Fail "run_todo_review_for_morning fehlt in main.py."
}

if ($mainText -notmatch "todo_review_result = run_todo_review_for_morning\(config\)") {
    Fail "Morning-Routine-Aufruf für TODO Review fehlt in main.py."
}

if (Test-Path $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json

    if (-not $config.todoReview) {
        Fail "todoReview fehlt in desktop-agent/config.json."
    }

    if ($config.todoReview.applyDuringMorningRoutine -ne $false) {
        Fail "applyDuringMorningRoutine muss standardmäßig false sein."
    }
}

Write-Host "[OK] Morning TODO Review Integration Test erfolgreich." -ForegroundColor Green
