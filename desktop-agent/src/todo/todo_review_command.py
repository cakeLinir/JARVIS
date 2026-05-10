from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from todo.todo_review import create_review_files  # noqa: E402


LogFn = Callable[[str, str], None]


def _noop_log(level: str, message: str) -> None:
    _ = (level, message)


def _safe_log(log: LogFn | None, level: str, message: str) -> None:
    if log is None:
        return

    try:
        log(level, message)
    except Exception:
        return


def find_repo_root(start: str | Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()

    candidates = [current, *current.parents]

    for candidate in candidates:
        if (
            (candidate / "desktop-agent" / "src" / "todo" / "todo_review.py").exists()
            and (candidate / "data").exists()
        ):
            return candidate

    raise FileNotFoundError(
        "JARVIS RepoRoot konnte nicht gefunden werden. "
        "Erwartet desktop-agent/src/todo/todo_review.py und data/."
    )


def _resolve_path(repo_root: Path, value: str | Path | None, default_relative: str) -> Path:
    if value is None or not str(value).strip():
        return (repo_root / default_relative).resolve()

    path = Path(value).expanduser()

    if path.is_absolute():
        return path.resolve()

    return (repo_root / path).resolve()


def run_agent_todo_review(
    repo_root: str | Path | None = None,
    todo_path: str | Path | None = None,
    review_out: str | Path | None = None,
    schedule_out: str | Path | None = None,
    apply_to_todo: bool = False,
    apply_log_out: str | Path | None = None,
    log: LogFn | None = None,
) -> dict[str, Any]:
    logger = log or _noop_log
    resolved_repo_root = find_repo_root(repo_root)

    resolved_todo_path = _resolve_path(resolved_repo_root, todo_path, "data/todo.md")
    resolved_review_out = _resolve_path(resolved_repo_root, review_out, "data/todo.review.json")
    resolved_schedule_out = _resolve_path(resolved_repo_root, schedule_out, "data/todo.schedule.json")
    resolved_apply_log_out = _resolve_path(resolved_repo_root, apply_log_out, "data/todo.apply-log.json")
    resolved_backup_dir = (resolved_repo_root / "data" / "backups").resolve()

    if not resolved_todo_path.exists():
        message = f"TODO-Datei nicht gefunden: {resolved_todo_path}"
        _safe_log(logger, "ERROR", message)

        return {
            "ok": False,
            "errorCode": "todo_file_missing",
            "message": message,
            "repoRoot": str(resolved_repo_root),
            "todoPath": str(resolved_todo_path),
        }

    _safe_log(
        logger,
        "INFO",
        "Agent TODO Review startet"
        + (" mit Apply." if apply_to_todo else " ohne Apply."),
    )

    try:
        result = create_review_files(
            todo_path=resolved_todo_path,
            review_path=resolved_review_out,
            schedule_path=resolved_schedule_out,
            apply=apply_to_todo,
            backup_dir=resolved_backup_dir,
            apply_log_path=resolved_apply_log_out if apply_to_todo else None,
        )
    except Exception as exc:
        message = f"Agent TODO Review fehlgeschlagen: {exc}"
        _safe_log(logger, "ERROR", message)

        return {
            "ok": False,
            "errorCode": "todo_review_failed",
            "message": message,
            "repoRoot": str(resolved_repo_root),
            "todoPath": str(resolved_todo_path),
        }

    review = result.get("review") or {}
    schedule = result.get("schedule") or {}
    apply_result = result.get("applyResult")

    summary = {
        "sourceItems": review.get("summary", {}).get("sourceItems", 0),
        "openItems": review.get("summary", {}).get("openItems", 0),
        "completedItemsIgnored": review.get("summary", {}).get("completedItemsIgnored", 0),
        "scheduledItems": schedule.get("summary", {}).get("scheduledItems", 0),
        "applied": apply_result is not None,
        "itemsWritten": apply_result.get("itemsWritten", 0) if isinstance(apply_result, dict) else 0,
    }

    _safe_log(
        logger,
        "OK",
        "Agent TODO Review abgeschlossen: "
        f"openItems={summary['openItems']}, "
        f"scheduledItems={summary['scheduledItems']}, "
        f"applied={summary['applied']}",
    )

    return {
        "ok": True,
        "errorCode": None,
        "message": "TODO Review abgeschlossen.",
        "repoRoot": str(resolved_repo_root),
        "todoPath": str(resolved_todo_path),
        "reviewPath": str(resolved_review_out),
        "schedulePath": str(resolved_schedule_out),
        "applyLogPath": str(resolved_apply_log_out) if apply_to_todo else None,
        "backupDir": str(resolved_backup_dir),
        "summary": summary,
        "applyResult": apply_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Agent TODO Review Command")
    parser.add_argument("--repo-root", required=False, help="JARVIS RepoRoot. Standard: Auto-Erkennung.")
    parser.add_argument("--todo", required=False, help="Pfad zur TODO-Datei. Standard: data/todo.md")
    parser.add_argument("--review-out", required=False, help="Pfad zu todo.review.json.")
    parser.add_argument("--schedule-out", required=False, help="Pfad zu todo.schedule.json.")
    parser.add_argument("--apply-log-out", required=False, help="Pfad zu todo.apply-log.json.")
    parser.add_argument("--apply", action="store_true", help="TODO-Datei nach Backup überarbeiten.")

    args = parser.parse_args()

    def cli_log(level: str, message: str) -> None:
        print(f"[{level}] {message}")

    result = run_agent_todo_review(
        repo_root=args.repo_root,
        todo_path=args.todo,
        review_out=args.review_out,
        schedule_out=args.schedule_out,
        apply_to_todo=args.apply,
        apply_log_out=args.apply_log_out,
        log=cli_log,
    )

    print("--- RESULT ---")
    print(json.dumps(result, ensure_ascii=True, indent=2))

    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
