param(
    [string]$RepoRoot = (Resolve-Path ".").Path,
    [string]$ProjectPath = ""
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 2
}

$repoRootResolved = (Resolve-Path $RepoRoot).Path
$agentRoot = Join-Path $repoRootResolved "desktop-agent"
$agentSrc = Join-Path $agentRoot "src"
$analyzer = Join-Path $agentSrc "integrations\project_analyzer.py"

if (-not (Test-Path $analyzer)) {
    Fail "project_analyzer.py nicht gefunden: $analyzer"
}

if (-not $ProjectPath.Trim()) {
    $ProjectPath = $repoRootResolved
}

Push-Location $agentRoot
try {
    Write-Host "[INFO] Python Compile..." -ForegroundColor Cyan
    py -3 -m py_compile "src\main.py" "src\integrations\project_analyzer.py"

    if ($LASTEXITCODE -ne 0) {
        Fail "py_compile fehlgeschlagen."
    }

    Write-Host "[INFO] Analyzer Smoke-Test..." -ForegroundColor Cyan

    $script = @"
from pathlib import Path
import sys

project_path = Path(sys.argv[1])
agent_src = sys.argv[2]

sys.path.insert(0, agent_src)

from integrations.project_analyzer import analyze_project, build_human_summary

def log(level, message):
    print(f"[{level}] {message}")

analysis = analyze_project(project_path, log)
print("--- SUMMARY ---")
print(build_human_summary(analysis))
print("--- COUNTS ---")
print("todoFiles", len(analysis.get("todoFiles", [])))
print("todoComments", len(analysis.get("todoComments", [])))
print("structure", len(analysis.get("structure", [])))

blocked_fragments = [
    ".jarvis-patch-backups",
    "node_modules",
    "dashboard/dist",
    "backend/dist",
]

combined = "\n".join(
    list(analysis.get("todoFiles", []))
    + list(analysis.get("todoComments", []))
    + list(analysis.get("structure", []))
)

found_blocked = [fragment for fragment in blocked_fragments if fragment in combined.replace("\\", "/")]

if found_blocked:
    print("--- BLOCKED FRAGMENTS FOUND ---")
    for fragment in found_blocked:
        print(fragment)
    raise SystemExit(3)
"@

    $temp = Join-Path $env:TEMP ("jarvis_project_analyzer_test_" + [guid]::NewGuid().ToString("N") + ".py")
    Set-Content -LiteralPath $temp -Value $script -Encoding UTF8

    try {
        py -3 $temp $ProjectPath $agentSrc

        if ($LASTEXITCODE -ne 0) {
            Fail "Analyzer Smoke-Test fehlgeschlagen."
        }
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[OK] Project Analyzer Test erfolgreich." -ForegroundColor Green
}
finally {
    Pop-Location
}
