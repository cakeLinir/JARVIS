from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


@dataclass(frozen=True)
class TodoSourceItem:
    id: str
    source_line: int
    original_text: str
    completed: bool


@dataclass(frozen=True)
class TodoReviewItem:
    id: str
    source_id: str
    source_line: int
    original_text: str
    proposed_text: str
    priority: str
    recommended_period: str
    status: str
    reason: str


@dataclass(frozen=True)
class TodoScheduleItem:
    id: str
    review_item_id: str
    title: str
    period: str
    planned_for: str | None
    status: str
    requires_confirmation: bool


CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+(?P<text>.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
NESTED_CHECKBOX_RE = re.compile(r"^\s*\[(?P<state>[ xX])\]\s+(?P<text>.+?)\s*$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def local_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def stable_id(*parts: str, length: int = 16) -> str:
    payload = "|".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:length]


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)

    return digest.hexdigest()


def clean_task_text(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = cleaned.replace("\\[", "[").replace("\\]", "]")
    cleaned = cleaned.strip("-*[] ")

    nested_match = NESTED_CHECKBOX_RE.match(cleaned)
    if nested_match:
        cleaned = nested_match.group("text").strip()

    if not cleaned:
        return cleaned

    return cleaned[0].upper() + cleaned[1:]

def parse_markdown_todos(todo_path: Path) -> list[TodoSourceItem]:
    if not todo_path.exists():
        raise FileNotFoundError(f"TODO-Datei nicht gefunden: {todo_path}")

    lines = todo_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    items: list[TodoSourceItem] = []

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()

        if not stripped:
            continue

        if stripped.startswith("#") or stripped.startswith("<!--"):
            continue

        normalized_line = raw_line.replace("\\[", "[").replace("\\]", "]")

        completed = False
        task_text: str | None = None

        checkbox_match = CHECKBOX_RE.match(normalized_line)
        if checkbox_match:
            completed = checkbox_match.group("state").lower() == "x"
            task_text = checkbox_match.group("text")

            nested_match = NESTED_CHECKBOX_RE.match(task_text)
            if nested_match:
                completed = nested_match.group("state").lower() == "x"
                task_text = nested_match.group("text")
        else:
            bullet_match = BULLET_RE.match(normalized_line)
            if bullet_match:
                task_text = bullet_match.group("text")

                nested_match = NESTED_CHECKBOX_RE.match(task_text)
                if nested_match:
                    completed = nested_match.group("state").lower() == "x"
                    task_text = nested_match.group("text")
            elif line_number > 1:
                task_text = stripped.replace("\\[", "[").replace("\\]", "]")

                nested_match = NESTED_CHECKBOX_RE.match(task_text)
                if nested_match:
                    completed = nested_match.group("state").lower() == "x"
                    task_text = nested_match.group("text")

        if task_text is None:
            continue

        cleaned = clean_task_text(task_text)

        if not cleaned:
            continue

        source_id = stable_id(str(todo_path.resolve()), str(line_number), cleaned)

        items.append(
            TodoSourceItem(
                id=source_id,
                source_line=line_number,
                original_text=cleaned,
                completed=completed,
            )
        )

    return items

def infer_priority(text: str) -> tuple[str, str]:
    normalized = text.lower()

    high_markers = (
        "dringend",
        "heute",
        "deadline",
        "fehler",
        "bug",
        "fix",
        "security",
        "sicherheit",
        "deploy",
        "backend",
        "vps",
        "auth",
    )

    low_markers = (
        "später",
        "optional",
        "irgendwann",
        "idee",
        "nice to have",
    )

    if any(marker in normalized for marker in high_markers):
        return "high", "Enthält einen Hinweis auf zeitkritische oder systemrelevante Arbeit."

    if any(marker in normalized for marker in low_markers):
        return "low", "Wirkt optional oder explizit auf später verschiebbar."

    return "normal", "Keine eindeutigen Dringlichkeitsmarker erkannt."


def infer_period(priority: str) -> str:
    if priority == "high":
        return "today_next_available"

    if priority == "low":
        return "later_today_or_backlog"

    return "later_today"


def propose_text(original_text: str) -> str:
    text = clean_task_text(original_text)

    replacements = {
        "jarvis": "JARVIS",
        "todo": "TODO",
        "vps": "VPS",
        "backend": "Backend",
        "frontend": "Frontend",
        "dashboard": "Dashboard",
        "discord": "Discord",
        "openai": "OpenAI",
    }

    words = text.split()
    normalized_words: list[str] = []

    for word in words:
        stripped = word.strip()
        lower = stripped.lower().strip(".,:;!?")

        if lower in replacements:
            punctuation = stripped[len(stripped.rstrip(".,:;!?")) :]
            normalized_words.append(replacements[lower] + punctuation)
        else:
            normalized_words.append(stripped)

    proposed = " ".join(normalized_words).strip()

    if not proposed:
        proposed = text

    if len(proposed) > 120:
        proposed = proposed[:117].rstrip() + "..."

    return proposed


def build_review(todo_path: Path) -> dict[str, Any]:
    todo_path = todo_path.resolve()
    source_items = parse_markdown_todos(todo_path)
    review_items: list[TodoReviewItem] = []

    for source in source_items:
        if source.completed:
            continue

        priority, reason = infer_priority(source.original_text)
        review_id = stable_id("review", source.id, source.original_text)

        review_items.append(
            TodoReviewItem(
                id=review_id,
                source_id=source.id,
                source_line=source.source_line,
                original_text=source.original_text,
                proposed_text=propose_text(source.original_text),
                priority=priority,
                recommended_period=infer_period(priority),
                status="proposed",
                reason=reason,
            )
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "jarvis.todo.review",
        "createdAt": utc_now_iso(),
        "sourcePath": str(todo_path),
        "sourceSha256": file_sha256(todo_path),
        "policy": {
            "autoApply": False,
            "applyAllowed": True,
            "applyRequiresBackup": True,
            "requiresUserConfirmation": True,
            "planner": "deterministic-v2",
            "openAiUsed": False,
        },
        "summary": {
            "sourceItems": len(source_items),
            "openItems": len(review_items),
            "completedItemsIgnored": len([item for item in source_items if item.completed]),
        },
        "items": [asdict(item) for item in review_items],
    }


def build_schedule(review: dict[str, Any]) -> dict[str, Any]:
    schedule_items: list[TodoScheduleItem] = []

    for item in review.get("items", []):
        schedule_id = stable_id("schedule", str(item.get("id", "")), str(item.get("proposed_text", "")))

        schedule_items.append(
            TodoScheduleItem(
                id=schedule_id,
                review_item_id=str(item["id"]),
                title=str(item["proposed_text"]),
                period=str(item.get("recommended_period", "later_today")),
                planned_for=None,
                status="pending",
                requires_confirmation=True,
            )
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "jarvis.todo.schedule",
        "createdAt": utc_now_iso(),
        "sourceReviewCreatedAt": review.get("createdAt"),
        "policy": {
            "autoStart": False,
            "requiresUserConfirmation": True,
            "deferredExecution": True,
        },
        "summary": {
            "scheduledItems": len(schedule_items),
            "pendingItems": len([item for item in schedule_items if item.status == "pending"]),
        },
        "items": [asdict(item) for item in schedule_items],
    }


def render_review_as_markdown(review: dict[str, Any]) -> str:
    created_at = review.get("createdAt", utc_now_iso())
    items = review.get("items", [])

    lines: list[str] = [
        "# TODO für heute",
        "",
        f"<!-- Überarbeitet durch JARVIS am {created_at}. -->",
        "<!-- Quelle wurde vor dem Überschreiben gesichert. -->",
        "",
    ]

    if not items:
        lines.append("<!-- Keine offenen TODOs gefunden. -->")
        lines.append("")
        return "\n".join(lines)

    groups = [
        ("Priorität hoch", "high"),
        ("Später heute", "normal"),
        ("Optional / Backlog", "low"),
    ]

    for heading, priority in groups:
        group_items = [item for item in items if item.get("priority") == priority]

        if not group_items:
            continue

        lines.append(f"## {heading}")
        lines.append("")

        for item in group_items:
            text = str(item.get("proposed_text") or item.get("original_text") or "").strip()

            if not text:
                continue

            lines.append(f"- [ ] {text}")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def create_backup(todo_path: Path, backup_dir: Path | None = None) -> Path:
    if not todo_path.exists():
        raise FileNotFoundError(f"TODO-Datei nicht gefunden: {todo_path}")

    if backup_dir is None:
        backup_dir = todo_path.parent / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_name = f"{todo_path.name}.backup-{local_timestamp()}"
    backup_path = backup_dir / backup_name

    shutil.copy2(todo_path, backup_path)

    return backup_path


def apply_review_to_todo(todo_path: Path, review: dict[str, Any], backup_dir: Path | None = None) -> dict[str, Any]:
    todo_path = todo_path.resolve()
    before_hash = file_sha256(todo_path)
    backup_path = create_backup(todo_path, backup_dir)
    rendered = render_review_as_markdown(review)

    todo_path.write_text(rendered, encoding="utf-8-sig", newline="\n")

    after_hash = file_sha256(todo_path)

    return {
        "appliedAt": utc_now_iso(),
        "todoPath": str(todo_path),
        "backupPath": str(backup_path.resolve()),
        "beforeSha256": before_hash,
        "afterSha256": after_hash,
        "itemsWritten": len(review.get("items", [])),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def create_review_files(
    todo_path: Path,
    review_path: Path,
    schedule_path: Path | None = None,
    apply: bool = False,
    backup_dir: Path | None = None,
    apply_log_path: Path | None = None,
) -> dict[str, Any]:
    review = build_review(todo_path)
    write_json(review_path, review)

    schedule: dict[str, Any] | None = None

    if schedule_path is not None:
        schedule = build_schedule(review)
        write_json(schedule_path, schedule)

    apply_result: dict[str, Any] | None = None

    if apply:
        apply_result = apply_review_to_todo(todo_path, review, backup_dir=backup_dir)

        if apply_log_path is not None:
            write_json(
                apply_log_path,
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "kind": "jarvis.todo.apply-log",
                    **apply_result,
                },
            )

    return {
        "reviewPath": str(review_path.resolve()),
        "schedulePath": str(schedule_path.resolve()) if schedule_path else None,
        "applyLogPath": str(apply_log_path.resolve()) if apply_log_path else None,
        "review": review,
        "schedule": schedule,
        "applyResult": apply_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS TODO Review Generator")
    parser.add_argument("--todo", required=True, help="Pfad zur Markdown TODO-Datei.")
    parser.add_argument("--review-out", required=True, help="Zielpfad für todo.review.json.")
    parser.add_argument("--schedule-out", required=False, help="Optionaler Zielpfad für todo.schedule.json.")
    parser.add_argument("--apply", action="store_true", help="Überarbeitet die TODO-Datei nach Backup direkt.")
    parser.add_argument("--backup-dir", required=False, help="Optionaler Backup-Ordner.")
    parser.add_argument("--apply-log-out", required=False, help="Optionaler Pfad für Apply-Log JSON.")

    args = parser.parse_args()

    todo_path = Path(args.todo)
    review_path = Path(args.review_out)
    schedule_path = Path(args.schedule_out) if args.schedule_out else None
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    apply_log_path = Path(args.apply_log_out) if args.apply_log_out else None

    result = create_review_files(
        todo_path=todo_path,
        review_path=review_path,
        schedule_path=schedule_path,
        apply=args.apply,
        backup_dir=backup_dir,
        apply_log_path=apply_log_path,
    )

    review = result["review"]
    schedule = result["schedule"]
    apply_result = result["applyResult"]

    print("[OK] TODO Review erstellt.")
    print(f"Review: {result['reviewPath']}")
    print(f"Offene Vorschläge: {review['summary']['openItems']}")

    if schedule is not None:
        print(f"Schedule: {result['schedulePath']}")
        print(f"Geplante Einträge: {schedule['summary']['scheduledItems']}")

    if apply_result is not None:
        print("[OK] TODO-Datei überarbeitet.")
        print(f"Backup: {apply_result['backupPath']}")
        print(f"Geschriebene Einträge: {apply_result['itemsWritten']}")

        if result["applyLogPath"]:
            print(f"Apply-Log: {result['applyLogPath']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
