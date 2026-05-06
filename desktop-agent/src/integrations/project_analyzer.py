import subprocess
from pathlib import Path
from typing import Any, Callable


LogFn = Callable[[str, str], None]

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".turbo",
}


ProjectAnalysis = dict[str, Any]


def run_command(command: list[str], cwd: Path, timeout_seconds: int = 10) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()

        if result.returncode != 0:
            return False, error if error else output

        return True, output

    except FileNotFoundError:
        return False, f"Command nicht gefunden: {command[0]}"

    except subprocess.TimeoutExpired:
        return False, f"Command Timeout nach {timeout_seconds}s: {' '.join(command)}"

    except Exception as exc:
        return False, str(exc)


def read_file_preview(path: Path, max_lines: int = 20) -> list[str]:
    if not path.exists() or not path.is_file():
        return []

    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        return lines[:max_lines]
    except Exception:
        return []


def find_files(project_path: Path, names: list[str]) -> list[Path]:
    found: list[Path] = []
    wanted = [name.lower() for name in names]

    for path in project_path.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if path.is_file() and path.name.lower() in wanted:
            found.append(path)

    return found[:10]


def find_todo_comments(project_path: Path, max_items: int = 30) -> list[str]:
    results: list[str] = []

    allowed_suffixes = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".md",
        ".ps1",
        ".yml",
        ".yaml",
    }

    for path in project_path.rglob("*"):
        if len(results) >= max_items:
            break

        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue

        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except Exception:
            continue

        for index, line in enumerate(lines, start=1):
            upper = line.upper()

            if "TODO" in upper or "FIXME" in upper:
                relative = path.relative_to(project_path)
                results.append(f"{relative}:{index}: {line.strip()}")

                if len(results) >= max_items:
                    break

    return results


def get_project_tree(project_path: Path, max_items: int = 80) -> list[str]:
    items: list[str] = []

    for path in sorted(project_path.rglob("*")):
        if len(items) >= max_items:
            break

        relative_parts = path.relative_to(project_path).parts

        if any(part in IGNORED_DIRS for part in relative_parts):
            continue

        depth = len(relative_parts)

        if depth > 3:
            continue

        prefix = "  " * (depth - 1)
        suffix = "/" if path.is_dir() else ""

        items.append(f"{prefix}{path.name}{suffix}")

    return items


def build_human_summary(analysis: ProjectAnalysis) -> str:
    if not analysis.get("ok"):
        return str(analysis.get("error", "Projektanalyse fehlgeschlagen."))

    parts: list[str] = [f"Projekt: {analysis.get('path')}"]

    git_status = analysis.get("gitStatus", [])
    if analysis.get("hasGit"):
        if git_status:
            parts.append(f"Git: {len(git_status)} lokale Änderung(en).")
        else:
            parts.append("Git: Arbeitsverzeichnis sauber.")
    else:
        parts.append("Git: kein Repository erkannt.")

    commits = analysis.get("recentCommits", [])
    if commits:
        parts.append(f"Letzter Commit: {commits[0]}")

    todos = analysis.get("todoComments", [])
    if todos:
        parts.append(f"Offene TODO/FIXME-Kommentare: {len(todos)}.")
    else:
        parts.append("Keine TODO/FIXME-Kommentare gefunden.")

    todo_files = analysis.get("todoFiles", [])
    if todo_files:
        parts.append("TODO-Dateien: " + ", ".join(todo_files[:3]))

    return " ".join(parts)


def analyze_project(project_path_value: str | None, log: LogFn) -> ProjectAnalysis:
    if not project_path_value:
        message = "Kein Projektpfad konfiguriert."
        log("WARN", message)
        return {"ok": False, "error": message}

    project_path = Path(project_path_value)

    if not project_path.exists():
        message = f"Projektpfad existiert nicht: {project_path}"
        log("ERROR", message)
        return {"ok": False, "error": message, "path": str(project_path)}

    if not project_path.is_dir():
        message = f"Projektpfad ist kein Ordner: {project_path}"
        log("ERROR", message)
        return {"ok": False, "error": message, "path": str(project_path)}

    log("INFO", f"Projektanalyse startet: {project_path}")

    analysis: ProjectAnalysis = {
        "ok": True,
        "path": str(project_path),
        "hasGit": (project_path / ".git").exists(),
        "gitStatus": [],
        "recentCommits": [],
        "readmeFiles": [],
        "readmePreview": [],
        "todoFiles": [],
        "todoComments": [],
        "tree": [],
        "warnings": [],
    }

    if analysis["hasGit"]:
        ok, output = run_command(["git", "status", "--short"], project_path)

        if ok:
            analysis["gitStatus"] = output.splitlines() if output else []
            if output:
                log("PROJECT", "Git Status: Es gibt lokale Änderungen.")
                for line in output.splitlines()[:20]:
                    log("PROJECT", f"  {line}")
            else:
                log("PROJECT", "Git Status: Arbeitsverzeichnis sauber.")
        else:
            analysis["warnings"].append(f"Git Status konnte nicht gelesen werden: {output}")
            log("WARN", f"Git Status konnte nicht gelesen werden: {output}")

        ok, output = run_command(["git", "log", "--oneline", "-5"], project_path)

        if ok and output:
            analysis["recentCommits"] = output.splitlines()
            log("PROJECT", "Letzte Commits:")
            for line in analysis["recentCommits"]:
                log("PROJECT", f"  {line}")
        elif not ok:
            analysis["warnings"].append(f"Git Log konnte nicht gelesen werden: {output}")
            log("WARN", f"Git Log konnte nicht gelesen werden: {output}")

    else:
        log("PROJECT", "Kein .git-Ordner gefunden. Git-Analyse übersprungen.")

    readme_files = find_files(project_path, ["README.md", "readme.md"])
    analysis["readmeFiles"] = [str(file.relative_to(project_path)) for file in readme_files]
    if readme_files:
        readme = readme_files[0]
        log("PROJECT", f"README gefunden: {readme.relative_to(project_path)}")

        preview = read_file_preview(readme, max_lines=12)
        analysis["readmePreview"] = [line.strip() for line in preview if line.strip()]
        for line in analysis["readmePreview"]:
            log("PROJECT", f"  README: {line}")
    else:
        log("PROJECT", "Keine README.md gefunden.")

    todo_files = find_files(project_path, ["TODO.md", "todo.md"])
    analysis["todoFiles"] = [str(file.relative_to(project_path)) for file in todo_files]
    if todo_files:
        log("PROJECT", "TODO-Dateien gefunden:")
        for file in todo_files:
            log("PROJECT", f"  {file.relative_to(project_path)}")
    else:
        log("PROJECT", "Keine TODO.md gefunden.")

    comments = find_todo_comments(project_path)
    analysis["todoComments"] = comments
    if comments:
        log("PROJECT", "Offene TODO/FIXME-Kommentare:")
        for item in comments:
            log("PROJECT", f"  {item}")
    else:
        log("PROJECT", "Keine TODO/FIXME-Kommentare gefunden.")

    tree = get_project_tree(project_path)
    analysis["tree"] = tree
    if tree:
        log("PROJECT", "Projektstruktur:")
        for item in tree[:50]:
            log("PROJECT", f"  {item}")

    analysis["summary"] = build_human_summary(analysis)
    log("INFO", "Projektanalyse abgeschlossen.")
    return analysis
