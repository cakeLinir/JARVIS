import subprocess
from pathlib import Path
from typing import Callable


LogFn = Callable[[str, str], None]


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

    ignored_dirs = {
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

    for path in project_path.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue

        if path.is_file() and path.name.lower() in [name.lower() for name in names]:
            found.append(path)

    return found[:10]


def find_todo_comments(project_path: Path, max_items: int = 30) -> list[str]:
    results: list[str] = []

    ignored_dirs = {
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

        if any(part in ignored_dirs for part in path.parts):
            continue

        if not path.is_file():
            continue

        if path.suffix.lower() not in allowed_suffixes:
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

    ignored_dirs = {
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

    for path in sorted(project_path.rglob("*")):
        if len(items) >= max_items:
            break

        relative_parts = path.relative_to(project_path).parts

        if any(part in ignored_dirs for part in relative_parts):
            continue

        depth = len(relative_parts)

        if depth > 3:
            continue

        prefix = "  " * (depth - 1)
        suffix = "/" if path.is_dir() else ""

        items.append(f"{prefix}{path.name}{suffix}")

    return items


def analyze_project(project_path_value: str | None, log: LogFn) -> None:
    if not project_path_value:
        log("WARN", "Kein Projektpfad konfiguriert.")
        return

    project_path = Path(project_path_value)

    if not project_path.exists():
        log("ERROR", f"Projektpfad existiert nicht: {project_path}")
        return

    if not project_path.is_dir():
        log("ERROR", f"Projektpfad ist kein Ordner: {project_path}")
        return

    log("INFO", f"Projektanalyse startet: {project_path}")

    git_dir = project_path / ".git"

    if git_dir.exists():
        ok, output = run_command(["git", "status", "--short"], project_path)

        if ok:
            if output:
                log("PROJECT", "Git Status: Es gibt lokale Änderungen.")
                for line in output.splitlines()[:20]:
                    log("PROJECT", f"  {line}")
            else:
                log("PROJECT", "Git Status: Arbeitsverzeichnis sauber.")
        else:
            log("WARN", f"Git Status konnte nicht gelesen werden: {output}")

        ok, output = run_command(["git", "log", "--oneline", "-5"], project_path)

        if ok and output:
            log("PROJECT", "Letzte Commits:")
            for line in output.splitlines():
                log("PROJECT", f"  {line}")
        elif not ok:
            log("WARN", f"Git Log konnte nicht gelesen werden: {output}")

    else:
        log("PROJECT", "Kein .git-Ordner gefunden. Git-Analyse übersprungen.")

    readme_files = find_files(project_path, ["README.md", "readme.md"])
    if readme_files:
        readme = readme_files[0]
        log("PROJECT", f"README gefunden: {readme.relative_to(project_path)}")

        preview = read_file_preview(readme, max_lines=12)
        for line in preview:
            clean = line.strip()
            if clean:
                log("PROJECT", f"  README: {clean}")
    else:
        log("PROJECT", "Keine README.md gefunden.")

    todo_files = find_files(project_path, ["TODO.md", "todo.md"])
    if todo_files:
        log("PROJECT", "TODO-Dateien gefunden:")
        for file in todo_files:
            log("PROJECT", f"  {file.relative_to(project_path)}")
    else:
        log("PROJECT", "Keine TODO.md gefunden.")

    comments = find_todo_comments(project_path)
    if comments:
        log("PROJECT", "Offene TODO/FIXME-Kommentare:")
        for item in comments:
            log("PROJECT", f"  {item}")
    else:
        log("PROJECT", "Keine TODO/FIXME-Kommentare gefunden.")

    tree = get_project_tree(project_path)
    if tree:
        log("PROJECT", "Projektstruktur:")
        for item in tree[:50]:
            log("PROJECT", f"  {item}")

    log("INFO", "Projektanalyse abgeschlossen.")
