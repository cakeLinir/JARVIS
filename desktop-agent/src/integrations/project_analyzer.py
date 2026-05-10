from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


LogFn = Callable[[str, str], None]


EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    ".runtime",
    "node_modules",
    ".jarvis-patch-backups",
    "logs",
    "dist",
    "__pycache__",
}

EXCLUDED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "config.local.json",
}

EXCLUDED_FILE_PREFIXES = {
    "config.local.json.backup-",
}

EXCLUDED_RELATIVE_PREFIXES = {
    "backend/.runtime",
    "backend/data",
    "backend/dist",
    "backend/node_modules",
    "dashboard/dist",
    "dashboard/node_modules",
    "desktop-agent/__pycache__",
}

TODO_NOISE_RELATIVE_FILES = {
    "desktop-agent/config.json",
    "desktop-agent/config.local.json",
    "desktop-agent/config.local.example.json",
    "docs/todo_system.md",
    "docs/local_agent_vps_connection.md",
    "docs/runtime_cleanup_analysis_noise.md",
    "docs/project_analyzer_refactor.md",
}

TEXT_FILE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".ps1",
    ".cmd",
    ".html",
    ".css",
}

TODO_MARKERS = (
    "todo:",
    "fixme:",
    "# todo",
    "# fixme",
    "// todo",
    "// fixme",
    "/* todo",
    "/* fixme",
    "<!-- todo",
    "<!-- fixme",
    "- todo:",
    "- fixme:",
    "* todo:",
    "* fixme:",
)

MAX_README_LINES = 8
MAX_COMMITS = 5
MAX_TODO_FILES = 10
MAX_TODO_COMMENTS = 20
MAX_STRUCTURE_ITEMS = 80
MAX_FILE_READ_BYTES = 256_000


@dataclass(frozen=True)
class ProjectAnalysis:
    project_path: str
    exists: bool
    git_available: bool
    git_dirty: bool
    git_status_lines: list[str]
    recent_commits: list[str]
    readme_lines: list[str]
    todo_files: list[str]
    todo_comments: list[str]
    structure: list[str]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectPath": self.project_path,
            "exists": self.exists,
            "gitAvailable": self.git_available,
            "gitDirty": self.git_dirty,
            "gitStatusLines": self.git_status_lines,
            "recentCommits": self.recent_commits,
            "readmeLines": self.readme_lines,
            "todoFiles": self.todo_files,
            "todoComments": self.todo_comments,
            "structure": self.structure,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _noop_log(level: str, message: str) -> None:
    _ = (level, message)


def _safe_log(log: LogFn | None, level: str, message: str) -> None:
    if log is None:
        return

    try:
        log(level, message)
    except Exception:
        return


def _normalize_path_text(value: Path | str) -> str:
    return str(value).replace("\\", "/").strip("/")


def _relative_text(project_path: Path, path_value: Path | str) -> str:
    candidate = Path(path_value)

    try:
        candidate = candidate.relative_to(project_path)
    except ValueError:
        pass

    return _normalize_path_text(candidate)


def _is_excluded_path(project_path: Path, path_value: Path | str) -> bool:
    candidate = Path(path_value)
    relative = _relative_text(project_path, candidate).lower()
    parts = {part for part in relative.split("/") if part}
    name = candidate.name.lower()

    if parts.intersection(EXCLUDED_DIR_NAMES):
        return True

    if name in EXCLUDED_FILE_NAMES:
        return True

    for prefix in EXCLUDED_FILE_PREFIXES:
        if name.startswith(prefix):
            return True

    for prefix in EXCLUDED_RELATIVE_PREFIXES:
        prefix_value = prefix.lower().strip("/")
        if relative == prefix_value or relative.startswith(prefix_value + "/"):
            return True

    return False


def _is_todo_noise_path(project_path: Path, path_value: Path | str) -> bool:
    relative = _relative_text(project_path, path_value).lower()

    if _is_excluded_path(project_path, path_value):
        return True

    return relative in TODO_NOISE_RELATIVE_FILES


def _is_todo_comment_line(stripped_line: str) -> bool:
    normalized = stripped_line.strip().lower()

    if not normalized:
        return False

    # Do not count the analyzer's own marker table entries.
    if normalized.startswith(('"', "'", "todo_markers", "explicit_prefixes")):
        return False

    # Only count explicit TODO/FIXME annotations at the beginning of a line.
    # This intentionally ignores normal identifiers or control flow such as:
    # todoProvider, buildTodoOverview, if todo:
    explicit_prefixes = (
        "todo:",
        "fixme:",
        "# todo",
        "# fixme",
        "// todo",
        "// fixme",
        "/* todo",
        "/* fixme",
        "<!-- todo",
        "<!-- fixme",
        "- todo:",
        "- fixme:",
        "* todo:",
        "* fixme:",
    )

    return normalized.startswith(explicit_prefixes)

def _iter_project_paths(project_path: Path) -> list[Path]:
    paths: list[Path] = []

    for candidate in project_path.rglob("*"):
        if _is_excluded_path(project_path, candidate):
            continue
        paths.append(candidate)

    return sorted(paths, key=lambda value: _relative_text(project_path, value).lower())


def _run_git(project_path: Path, args: list[str], timeout_seconds: int = 8) -> tuple[bool, list[str]]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return False, [str(exc)]

    output = (completed.stdout or completed.stderr or "").splitlines()
    output = [line.rstrip() for line in output if line.strip()]

    return completed.returncode == 0, output


def _read_text_lines(path: Path, max_lines: int | None = None) -> list[str]:
    try:
        if path.stat().st_size > MAX_FILE_READ_BYTES:
            return []
    except OSError:
        return []

    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except Exception:
        return []

    if max_lines is not None:
        return lines[:max_lines]

    return lines


def _collect_readme(project_path: Path) -> list[str]:
    readme = project_path / "README.md"

    if not readme.exists() or not readme.is_file():
        return []

    lines: list[str] = []

    for line in _read_text_lines(readme, MAX_README_LINES):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)

    return lines


def _collect_todo_files(project_path: Path, paths: list[Path]) -> list[str]:
    todo_files: list[str] = []

    for path in paths:
        if not path.is_file():
            continue

        name = path.name.lower()
        relative = _relative_text(project_path, path)

        if name in {"todo.md", "todos.md"} or name.startswith("todo."):
            if _is_excluded_path(project_path, path):
                continue
            todo_files.append(relative)

    return todo_files[:MAX_TODO_FILES]


def _collect_todo_comments(project_path: Path, paths: list[Path]) -> list[str]:
    comments: list[str] = []

    for path in paths:
        if len(comments) >= MAX_TODO_COMMENTS:
            break

        if not path.is_file():
            continue

        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue

        if _is_todo_noise_path(project_path, path):
            continue

        lines = _read_text_lines(path)

        for index, line in enumerate(lines, start=1):
            if len(comments) >= MAX_TODO_COMMENTS:
                break

            stripped = line.strip()

            if not _is_todo_comment_line(stripped):
                continue

            if path.name.lower() in {"todo.md", "todos.md"} and stripped.startswith("#"):
                continue

            relative = _relative_text(project_path, path)
            comments.append(f"{relative}:{index}: {stripped}")

    return comments


def _collect_structure(project_path: Path, paths: list[Path]) -> list[str]:
    structure: list[str] = []

    for path in paths:
        if len(structure) >= MAX_STRUCTURE_ITEMS:
            break

        relative = _relative_text(project_path, path)

        if not relative:
            continue

        depth = relative.count("/")
        if depth > 2:
            continue

        indent = "  " * depth
        suffix = "/" if path.is_dir() else ""
        name = relative.split("/")[-1]

        structure.append(f"{indent}{name}{suffix}")

    return structure


def _analyze_git(project_path: Path) -> tuple[bool, bool, list[str], list[str], list[str]]:
    warnings: list[str] = []
    git_dir = project_path / ".git"

    if not git_dir.exists():
        return False, False, [], [], ["Kein .git-Ordner gefunden. Git-Analyse übersprungen."]

    status_ok, status_lines = _run_git(project_path, ["status", "--porcelain"])

    if not status_ok:
        warnings.append("Git Status konnte nicht gelesen werden.")
        status_lines = []

    log_ok, commit_lines = _run_git(project_path, ["log", "--oneline", f"-{MAX_COMMITS}"])

    if not log_ok:
        warnings.append("Git Log konnte nicht gelesen werden.")
        commit_lines = []

    git_dirty = len(status_lines) > 0

    return True, git_dirty, status_lines, commit_lines, warnings


def analyze_project(project_path_value: str | Path | None, log: LogFn | None = None) -> dict[str, Any]:
    logger = log or _noop_log
    warnings: list[str] = []
    errors: list[str] = []

    if not project_path_value:
        message = "Projektpfad ist nicht konfiguriert."
        _safe_log(logger, "WARN", message)

        return ProjectAnalysis(
            project_path="",
            exists=False,
            git_available=False,
            git_dirty=False,
            git_status_lines=[],
            recent_commits=[],
            readme_lines=[],
            todo_files=[],
            todo_comments=[],
            structure=[],
            warnings=[message],
            errors=[],
        ).to_dict()

    project_path = Path(project_path_value).expanduser().resolve()

    _safe_log(logger, "INFO", f"Projektanalyse startet: {project_path}")

    if not project_path.exists() or not project_path.is_dir():
        message = f"Projektpfad nicht gefunden: {project_path}"
        _safe_log(logger, "ERROR", message)

        return ProjectAnalysis(
            project_path=str(project_path),
            exists=False,
            git_available=False,
            git_dirty=False,
            git_status_lines=[],
            recent_commits=[],
            readme_lines=[],
            todo_files=[],
            todo_comments=[],
            structure=[],
            warnings=[],
            errors=[message],
        ).to_dict()

    git_available, git_dirty, status_lines, recent_commits, git_warnings = _analyze_git(project_path)
    warnings.extend(git_warnings)

    if git_available:
        if git_dirty:
            _safe_log(logger, "PROJECT", "Git Status: Es gibt lokale Änderungen.")
            for line in status_lines[:20]:
                _safe_log(logger, "PROJECT", f"  {line}")
        else:
            _safe_log(logger, "PROJECT", "Git Status: Arbeitsverzeichnis sauber.")

        if recent_commits:
            _safe_log(logger, "PROJECT", "Letzte Commits:")
            for line in recent_commits:
                _safe_log(logger, "PROJECT", f"  {line}")
    else:
        for warning in git_warnings:
            _safe_log(logger, "PROJECT", warning)

    readme_lines = _collect_readme(project_path)

    if readme_lines:
        _safe_log(logger, "PROJECT", "README gefunden: README.md")
        for line in readme_lines:
            _safe_log(logger, "PROJECT", f"  README: {line}")
    else:
        _safe_log(logger, "PROJECT", "Keine README.md gefunden.")

    paths = _iter_project_paths(project_path)
    todo_files = _collect_todo_files(project_path, paths)
    todo_comments = _collect_todo_comments(project_path, paths)
    structure = _collect_structure(project_path, paths)

    if todo_files:
        _safe_log(logger, "PROJECT", "TODO-Dateien gefunden:")
        for file in todo_files:
            _safe_log(logger, "PROJECT", f"  {file}")
    else:
        _safe_log(logger, "PROJECT", "Keine TODO.md gefunden.")

    if todo_comments:
        _safe_log(logger, "PROJECT", "Offene TODO/FIXME-Kommentare:")
        for item in todo_comments:
            _safe_log(logger, "PROJECT", f"  {item}")
    else:
        _safe_log(logger, "PROJECT", "Keine TODO/FIXME-Kommentare gefunden.")

    if structure:
        _safe_log(logger, "PROJECT", "Projektstruktur:")
        for item in structure:
            _safe_log(logger, "PROJECT", f"  {item}")

    _safe_log(logger, "INFO", "Projektanalyse abgeschlossen.")

    return ProjectAnalysis(
        project_path=str(project_path),
        exists=True,
        git_available=git_available,
        git_dirty=git_dirty,
        git_status_lines=status_lines,
        recent_commits=recent_commits,
        readme_lines=readme_lines,
        todo_files=todo_files,
        todo_comments=todo_comments,
        structure=structure,
        warnings=warnings,
        errors=errors,
    ).to_dict()


def build_human_summary(analysis: dict[str, Any] | ProjectAnalysis) -> str:
    if isinstance(analysis, ProjectAnalysis):
        data = analysis.to_dict()
    else:
        data = analysis

    if not data.get("exists"):
        errors = data.get("errors") or []
        warnings = data.get("warnings") or []
        message = errors[0] if errors else warnings[0] if warnings else "Projektanalyse nicht verfügbar."
        return message

    parts: list[str] = []

    project_path = data.get("projectPath")
    if project_path:
        parts.append(f"Projekt: {project_path}")

    if data.get("gitAvailable"):
        if data.get("gitDirty"):
            count = len(data.get("gitStatusLines") or [])
            parts.append(f"Git: {count} lokale Änderung(en).")
        else:
            parts.append("Git: Arbeitsverzeichnis sauber.")
    else:
        parts.append("Git: nicht verfügbar.")

    commits = data.get("recentCommits") or []
    if commits:
        parts.append(f"Letzter Commit: {commits[0]}")

    todo_files = data.get("todoFiles") or []
    parts.append(f"TODO-Dateien: {len(todo_files)}.")

    todo_comments = data.get("todoComments") or []
    parts.append(f"Offene TODO/FIXME-Kommentare: {len(todo_comments)}.")

    warnings = data.get("warnings") or []
    if warnings:
        parts.append(f"Warnungen: {len(warnings)}.")

    errors = data.get("errors") or []
    if errors:
        parts.append(f"Fehler: {len(errors)}.")

    return " ".join(parts)
