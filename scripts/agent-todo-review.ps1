param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$TodoPath = "",
    [switch]$ApplyToTodo
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$commandModule = Join-Path $repoRootResolved "desktop-agent\src\todo\todo_review_command.py"

if (-not (Test-Path $commandModule)) {
    Fail "todo_review_command.py nicht gefunden: $commandModule"
}

$argsList = @(
    $commandModule,
    "--repo-root", $repoRootResolved
)

if ($TodoPath.Trim()) {
    $argsList += @("--todo", $TodoPath)
}

if ($ApplyToTodo) {
    $argsList += "--apply"
}

py -3 @argsList

if ($LASTEXITCODE -ne 0) {
    Fail "Agent TODO Review Command fehlgeschlagen."
}
