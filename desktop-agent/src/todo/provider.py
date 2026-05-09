from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal


LogFn = Callable[[str, str], None]

TodoStatus = Literal["open", "done", "cancelled"]


@dataclass(slots=True)
class TodoItem:
    id: str
    title: str
    status: TodoStatus = "open"
    dueDate: str | None = None
    priority: int = 3
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True

    upper = value.upper()
    markers = [
        "CHANGE_ME",
        "PATH\\TO",
        "C:\\\\PATH",
        "DEIN_USER",
        "EXAMPLE",
        "<",
        ">",
    ]
    return any(marker in upper for marker in markers)


def _resolve_path(path_value: str | None, log: LogFn, label: str) -> Path | None:
    if _is_placeholder(path_value):
        log("ERROR", f"KONFIGURATION_ERFORDERLICH: {label} fehlt oder ist noch ein Platzhalter.")
        return None

    return Path(str(path_value)).expanduser()


def _today_iso() -> str:
    return date.today().isoformat()


def _parse_markdown_items(path: Path, log: LogFn) -> list[TodoItem]:
    if not path.exists():
        log("ERROR", f"KONFIGURATION_ERFORDERLICH: TODO Markdown-Datei existiert nicht: {path}")
        return []

    items: list[TodoItem] = []

    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except Exception as exc:
        log("ERROR", f"TODO Markdown-Datei konnte nicht gelesen werden: {path} | {exc}")
        return []

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()

        if stripped.startswith("- [ ]"):
            title = stripped.replace("- [ ]", "", 1).strip()
            if title:
                items.append(
                    TodoItem(
                        id=f"md-{index}",
                        title=title,
                        status="open",
                        dueDate=None,
                        priority=3,
                        source="markdown",
                    )
                )

    return items


def _ensure_json_store(path: Path, log: LogFn) -> None:
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    seed = {
        "version": 1,
        "items": [
            {
                "id": "todo-001",
                "title": "JARVIS TODO-System konfigurieren",
                "status": "open",
                "dueDate": _today_iso(),
                "priority": 2,
                "source": "json",
            }
        ],
    }
    path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    log("INFO", f"TODO JSON-Datei erstellt: {path}")


def _parse_json_items(path: Path, log: LogFn) -> list[TodoItem]:
    _ensure_json_store(path, log)

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        log("ERROR", f"TODO JSON-Datei konnte nicht gelesen werden: {path} | {exc}")
        return []

    raw_items = raw.get("items", []) if isinstance(raw, dict) else raw

    if not isinstance(raw_items, list):
        log("ERROR", f"TODO JSON-Format ungültig: {path}")
        return []

    items: list[TodoItem] = []

    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        if not title:
            continue

        status = str(item.get("status", "open")).strip().lower()
        if status not in {"open", "done", "cancelled"}:
            status = "open"

        due_date = item.get("dueDate")
        due_date_value = str(due_date).strip() if due_date else None

        try:
            priority = int(item.get("priority", 3))
        except Exception:
            priority = 3

        items.append(
            TodoItem(
                id=str(item.get("id") or f"json-{index}"),
                title=title,
                status=status,  # type: ignore[arg-type]
                dueDate=due_date_value,
                priority=priority,
                source="json",
            )
        )

    return items


def _ensure_sqlite_store(path: Path, log: LogFn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                due_date TEXT NULL,
                priority INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        count = connection.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")
            connection.execute(
                """
                INSERT INTO todos (id, title, status, due_date, priority, created_at, updated_at)
                VALUES (?, ?, 'open', ?, 2, ?, ?)
                """,
                ("todo-001", "JARVIS SQLite TODO-System prüfen", _today_iso(), now, now),
            )

        connection.commit()

    log("INFO", f"TODO SQLite-Datenbank bereit: {path}")


def _parse_sqlite_items(path: Path, log: LogFn) -> list[TodoItem]:
    try:
        _ensure_sqlite_store(path, log)

        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, title, status, due_date, priority
                FROM todos
                ORDER BY
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC,
                    priority ASC,
                    created_at ASC
                """
            ).fetchall()

    except Exception as exc:
        log("ERROR", f"TODO SQLite-Datenbank konnte nicht gelesen werden: {path} | {exc}")
        return []

    items: list[TodoItem] = []
    for row in rows:
        status = str(row["status"] or "open").strip().lower()
        if status not in {"open", "done", "cancelled"}:
            status = "open"

        items.append(
            TodoItem(
                id=str(row["id"]),
                title=str(row["title"]),
                status=status,  # type: ignore[arg-type]
                dueDate=str(row["due_date"]) if row["due_date"] else None,
                priority=int(row["priority"] or 3),
                source="sqlite",
            )
        )

    return items


def get_todo_provider(config: dict[str, Any]) -> str:
    todo_config = config.get("todo", {})
    provider = str(todo_config.get("provider", "markdown")).strip().lower()

    if provider not in {"markdown", "json", "sqlite"}:
        return "markdown"

    return provider


def read_todo_items(config: dict[str, Any], log: LogFn) -> list[TodoItem]:
    todo_config = config.get("todo", {})
    provider_name = get_todo_provider(config)

    if provider_name == "markdown":
        path = _resolve_path(todo_config.get("markdownPath"), log, "todo.markdownPath")
        return _parse_markdown_items(path, log) if path else []

    if provider_name == "json":
        path = _resolve_path(todo_config.get("jsonPath"), log, "todo.jsonPath")
        return _parse_json_items(path, log) if path else []

    if provider_name == "sqlite":
        path = _resolve_path(todo_config.get("sqlitePath"), log, "todo.sqlitePath")
        return _parse_sqlite_items(path, log) if path else []

    log("ERROR", f"TODO Provider nicht unterstützt: {provider_name}")
    return []


def read_open_todo_titles(config: dict[str, Any], log: LogFn) -> list[str]:
    today = _today_iso()
    result: list[str] = []

    for item in read_todo_items(config, log):
        if item.status != "open":
            continue

        # MVP behavior: include items without dueDate and items due today or earlier.
        if item.dueDate and item.dueDate > today:
            continue

        result.append(item.title)

    return result


def open_todo_provider(config: dict[str, Any], log: LogFn) -> bool:
    todo_config = config.get("todo", {})
    provider_name = get_todo_provider(config)

    if provider_name == "markdown":
        path = _resolve_path(todo_config.get("markdownPath"), log, "todo.markdownPath")
    elif provider_name == "json":
        path = _resolve_path(todo_config.get("jsonPath"), log, "todo.jsonPath")
    elif provider_name == "sqlite":
        log("INFO", "TODO SQLite-Provider wird nicht direkt in Notepad geöffnet.")
        return False
    else:
        log("ERROR", f"TODO Provider nicht unterstützt: {provider_name}")
        return False

    if not path:
        return False

    if not path.exists() and provider_name == "json":
        _ensure_json_store(path, log)

    if not path.exists():
        log("ERROR", f"KONFIGURATION_ERFORDERLICH: TODO-Datei existiert nicht: {path}")
        return False

    try:
        subprocess.Popen(
            ["notepad.exe", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008,
            close_fds=True,
        )
        log("OK", f"TODO Provider geöffnet: {provider_name} | {path}")
        return True
    except Exception as exc:
        log("ERROR", f"TODO Provider konnte nicht geöffnet werden: {provider_name} | {path} | {exc}")
        return False


def get_todo_status(config: dict[str, Any], log: LogFn) -> dict[str, Any]:
    provider_name = get_todo_provider(config)
    items = read_todo_items(config, log)

    open_items = [item for item in items if item.status == "open"]
    today = _today_iso()
    due_items = [
        item for item in open_items
        if item.dueDate is None or item.dueDate <= today
    ]

    return {
        "provider": provider_name,
        "total": len(items),
        "open": len(open_items),
        "dueTodayOrUnscheduled": len(due_items),
        "items": [item.to_dict() for item in due_items[:20]],
    }
