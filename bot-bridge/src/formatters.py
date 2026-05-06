from typing import Any


def format_status(data: dict[str, Any]) -> str:
    status = data.get("status")

    if not status:
        return "JARVIS-Agent hat noch keinen Status ans Backend gesendet."

    agent_name = status.get("agentName", "unbekannt")
    hostname = status.get("hostname", "unbekannt")
    state = status.get("status", "unbekannt")
    timestamp = status.get("timestamp", "unbekannt")
    received_at = status.get("receivedAt", "unbekannt")

    return (
        "**JARVIS Status**\n"
        f"Agent: `{agent_name}`\n"
        f"Host: `{hostname}`\n"
        f"Status: `{state}`\n"
        f"Zeitpunkt Agent: `{timestamp}`\n"
        f"Empfangen Backend: `{received_at}`"
    )


def format_morning_log(data: dict[str, Any]) -> str:
    morning_log = data.get("morningLog")

    if not morning_log:
        return "Es liegt noch kein Morning-Log vor."

    started_apps = morning_log.get("startedApps", [])
    failed_apps = morning_log.get("failedApps", [])
    todos = morning_log.get("todos", [])
    project_summary = morning_log.get("projectSummary", "Keine Projektzusammenfassung vorhanden.")
    timestamp = morning_log.get("timestamp", "unbekannt")
    received_at = morning_log.get("receivedAt", "unbekannt")

    started_text = ", ".join(started_apps) if started_apps else "Keine"
    failed_text = ", ".join(failed_apps) if failed_apps else "Keine"

    todo_lines = "\n".join(f"- {item}" for item in todos[:10]) if todos else "Keine offenen TODOs."

    return (
        "**JARVIS Morning-Log**\n"
        f"Zeitpunkt Agent: `{timestamp}`\n"
        f"Empfangen Backend: `{received_at}`\n\n"
        f"**Gestartet:** {started_text}\n"
        f"**Fehlgeschlagen:** {failed_text}\n\n"
        f"**TODOs:**\n{todo_lines}\n\n"
        f"**Projekt:**\n{project_summary}"
    )


def shorten_for_discord(message: str, limit: int = 1900) -> str:
    if len(message) <= limit:
        return message

    return message[: limit - 20] + "\n... gekürzt"
