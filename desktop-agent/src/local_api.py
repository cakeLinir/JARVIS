from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

LogFn = Callable[[str, str], None]
ActionFn = Callable[[], None]
StopFn = Callable[[], None]

MAX_BODY_BYTES = 16 * 1024


def _is_usable_token(token: str | None) -> bool:
    if not token:
        return False
    raw = token.strip()
    upper = raw.upper()
    if not upper:
        return False
    markers = ["CHANGE_ME", "EXAMPLE", "PLACEHOLDER"]
    if any(marker in upper for marker in markers):
        return False
    return len(raw) >= 16


def _safe_config_status(config: dict[str, Any]) -> dict[str, Any]:
    backend_url = str(config.get("backendUrl", "")).strip()
    agent_token = str(config.get("agentToken", "")).strip()
    local_api = config.get("localApi", {})
    local_token = (
        str(local_api.get("token", "")).strip() if isinstance(local_api, dict) else ""
    )
    return {
        "backendUrlConfigured": bool(backend_url),
        "agentTokenConfigured": _is_usable_token(agent_token),
        "localApiTokenConfigured": _is_usable_token(local_token),
    }


def _get_todos_today(config: dict[str, Any], log: LogFn) -> list[dict[str, Any]]:
    try:
        from todo.sync_client import sync_todos_from_backend

        return sync_todos_from_backend(config, log)
    except Exception:
        # Offline-Fallback auf lokalen Provider
        try:
            from todo.provider import read_todo_items

            today_str = date.today().isoformat()
            items = read_todo_items(config, log)
            return [
                item.to_dict()
                for item in items
                if item.status == "open"
                and (not item.dueDate or item.dueDate <= today_str)
            ]
        except Exception as exc:
            log("WARN", f"Lokaler TODO-Fallback fehlgeschlagen: {exc}")
            return []


def _create_todo_via_sync(
    config: dict[str, Any],
    log: LogFn,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        from todo.sync_client import push_todo_to_backend

        return push_todo_to_backend(config, log, payload)
    except Exception as exc:
        log("WARN", f"TODO-Erstellen fehlgeschlagen: {exc}")
        return None


def _complete_todo_via_sync(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
) -> dict[str, Any] | None:
    try:
        from todo.sync_client import complete_todo_on_backend

        return complete_todo_on_backend(config, log, todo_id)
    except Exception as exc:
        log("WARN", f"TODO-Complete fehlgeschlagen: {exc}")
        return None


def _todo_status(config: dict[str, Any], log: LogFn) -> dict[str, Any]:
    try:
        from todo.provider import get_todo_status

        status = get_todo_status(config, log)
        return {
            "provider": status.get("provider"),
            "total": status.get("total"),
            "open": status.get("open"),
            "dueTodayOrUnscheduled": status.get("dueTodayOrUnscheduled"),
            "errorCode": status.get("errorCode"),
            "message": status.get("message"),
        }
    except Exception as exc:
        return {
            "provider": "unknown",
            "errorCode": "todo_status_failed",
            "message": str(exc),
        }


def _voice_status(config: dict[str, Any]) -> dict[str, Any]:
    try:
        from voice.controller import get_voice_status

        return get_voice_status(config).to_dict()
    except Exception as exc:
        return {
            "enabled": False,
            "mode": "unknown",
            "wakeWordEnabled": False,
            "sttProvider": "disabled",
            "ttsProvider": "disabled",
            "reason": f"Voice-Status konnte nicht gelesen werden: {exc}",
        }


class LocalApiServer:
    def __init__(
        self,
        config: dict[str, Any],
        host: str,
        port: int,
        token: str,
        log: LogFn,
        run_morning: ActionFn,
        stop_agent: StopFn,
        brain: Any = None,
        tool_executor: Any = None,
        speak_fn: Any = None,
    ) -> None:
        self.config = config
        self.host = host
        self.port = port
        self.token = token
        self.log = log
        self.run_morning = run_morning
        self.stop_agent = stop_agent
        self.brain = brain
        self.tool_executor = tool_executor
        self.speak_fn = speak_fn
        self.started_at = datetime.now().isoformat()
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def _health_payload(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "jarvis-local-agent",
            "startedAt": self.started_at,
            "now": datetime.now().isoformat(),
            "runtime": {
                "status": "online",
                "host": self.host,
                "port": self.port,
            },
            "configuration": _safe_config_status(self.config),
            "voice": _voice_status(self.config),
            "todo": _todo_status(self.config, self.log),
            "brain": {  # NEU
                "available": self.brain is not None,
                "historyTurns": (
                    self.brain.history_turns if self.brain is not None else 0
                ),
            },
        }

    def start(self) -> None:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                parent.log("LOCAL_API", format % args)

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self) -> bool:
                expected = f"Bearer {parent.token}"
                return self.headers.get("Authorization", "") == expected

            def _read_json_body(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                if length > MAX_BODY_BYTES:
                    raise ValueError(
                        f"request_body_too_large: max {MAX_BODY_BYTES} bytes"
                    )
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                if not raw:
                    return {}
                return json.loads(raw)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._send_json(200, parent._health_payload())
                    return

                if self.path == "/todos/today":
                    if not self._authorized():
                        self._send_json(
                            403,
                            {"ok": False, "error": "invalid_local_api_token"},
                        )
                        return
                    todos = _get_todos_today(parent.config, parent.log)
                    self._send_json(
                        200,
                        {"ok": True, "count": len(todos), "todos": todos},
                    )
                    return

                self._send_json(404, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized():
                    self._send_json(
                        403,
                        {"ok": False, "error": "invalid_local_api_token"},
                    )
                    return
                try:
                    body = self._read_json_body()
                except Exception as exc:
                    self._send_json(
                        400,
                        {
                            "ok": False,
                            "error": "invalid_json",
                            "message": str(exc),
                        },
                    )
                    return

                # ── POST /todos — neues TODO erstellen ────────────────────
                if self.path == "/todos":
                    title = str(body.get("title", "")).strip()
                    if not title:
                        self._send_json(400, {"ok": False, "error": "title_required"})
                        return
                    payload: dict[str, Any] = {
                        "title": title,
                        "source": str(body.get("source", "manual")),
                        "priority": int(body.get("priority", 3)),
                    }
                    for key in (
                        "dueDate",
                        "dueTime",
                        "category",
                        "description",
                        "reminderMinutes",
                    ):
                        if key in body:
                            payload[key] = body[key]
                    todo = _create_todo_via_sync(parent.config, parent.log, payload)
                    if todo:
                        self._send_json(201, {"ok": True, "todo": todo})
                    else:
                        self._send_json(
                            202,
                            {
                                "ok": True,
                                "queued": True,
                                "message": "TODO in Pending-Queue gespeichert.",
                            },
                        )
                    return

                # ── POST /todos/:id/complete ───────────────────────────────
                path_parts = self.path.strip("/").split("/")
                if (
                    len(path_parts) == 3
                    and path_parts[0] == "todos"
                    and path_parts[2] == "complete"
                ):
                    todo_id = path_parts[1]
                    result = _complete_todo_via_sync(parent.config, parent.log, todo_id)
                    if result:
                        self._send_json(200, {"ok": True, "todo": result})
                    else:
                        self._send_json(
                            202,
                            {
                                "ok": True,
                                "queued": True,
                                "message": ("Complete in Pending-Queue gespeichert."),
                            },
                        )
                    return

                # ── POST /actions/morning ─────────────────────────────────
                if self.path == "/actions/morning":
                    confirm = body.get("confirm")
                    if confirm != "START":
                        self._send_json(
                            400, {"ok": False, "error": "confirmation_required"}
                        )
                        return
                    threading.Thread(target=parent.run_morning, daemon=True).start()
                    self._send_json(
                        202,
                        {
                            "ok": True,
                            "accepted": True,
                            "action": "morning_routine",
                        },
                    )
                    return

                # ── POST /actions/stop ────────────────────────────────────
                if self.path == "/actions/stop":
                    confirm = body.get("confirm")
                    if confirm != "STOP":
                        self._send_json(
                            400, {"ok": False, "error": "confirmation_required"}
                        )
                        return
                    parent.stop_agent()
                    self._send_json(
                        202,
                        {"ok": True, "accepted": True, "action": "stop"},
                    )
                    return

                # ── POST /actions/chat — AI-Unterhaltung ──────────────────
                if self.path == "/actions/chat":
                    if parent.brain is None:
                        self._send_json(
                            503,
                            {
                                "ok": False,
                                "error": "brain_not_available",
                                "message": (
                                    "AI-Brain ist nicht initialisiert. "
                                    "Anthropic API-Key prüfen."
                                ),
                            },
                        )
                        return
                    text = str(body.get("text", "")).strip()
                    if not text:
                        self._send_json(400, {"ok": False, "error": "text_required"})
                        return
                    try:
                        tool_calls = parent.brain.process(text)
                        answer_text: str | None = None

                        for tc in tool_calls:
                            if tc["name"] == "answer":
                                answer_text = str(tc["input"].get("text", ""))
                                break

                        if answer_text is None and parent.tool_executor is not None:
                            feedback = parent.tool_executor(tool_calls)
                            if feedback:
                                answer_text = parent.brain.submit_tool_result(feedback)
                                if not answer_text and feedback:
                                    answer_text = feedback[0]["result"]

                        should_speak = body.get("speak", True)
                        if answer_text and should_speak and parent.speak_fn is not None:
                            try:
                                parent.speak_fn(answer_text)
                            except Exception as speak_exc:
                                parent.log(
                                    "WARN",
                                    f"TTS in chat-endpoint failed: {speak_exc}",
                                )

                        self._send_json(
                            200,
                            {
                                "ok": True,
                                "answer": answer_text,
                                "toolCalls": [
                                    {"name": tc["name"], "input": tc["input"]}
                                    for tc in tool_calls
                                ],
                                "historyTurns": parent.brain.history_turns,
                                "spoken": bool(
                                    answer_text and should_speak and parent.speak_fn
                                ),
                            },
                        )
                    except Exception as exc:
                        parent.log(
                            "ERROR",
                            f"Chat-Endpoint Fehler: {exc}",
                            errorCode="chat_endpoint_failed",
                        )
                        self._send_json(
                            500,
                            {
                                "ok": False,
                                "error": "chat_failed",
                                "message": str(exc),
                            },
                        )
                    return

                # ── POST /actions/chat/reset — History zurücksetzen ───────
                if self.path == "/actions/chat/reset":
                    if parent.brain is not None:
                        parent.brain.clear_history()
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "cleared": True,
                            "historyTurns": 0,
                        },
                    )
                    return

                self._send_json(404, {"ok": False, "error": "not_found"})

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.log(
            "INFO",
            f"Lokale Agent-API gestartet: http://{self.host}:{self.port}",
        )

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.log("INFO", "Lokale Agent-API beendet.")


def start_local_api(
    config: dict[str, Any],
    log: LogFn,
    run_morning: ActionFn,
    stop_agent: StopFn,
    brain: Any = None,
    tool_executor: Any = None,
    speak_fn: Any = None,
) -> LocalApiServer | None:
    local_api_config = config.get("localApi", {})
    if not isinstance(local_api_config, dict) or not local_api_config.get(
        "enabled", False
    ):
        log("INFO", "Lokale Agent-API deaktiviert.")
        return None

    host = str(local_api_config.get("host", "127.0.0.1")).strip()
    port = int(local_api_config.get("port", 8765))
    token = str(local_api_config.get("token", "")).strip()

    if host not in {"127.0.0.1", "localhost"}:
        log(
            "ERROR",
            f"SICHERHEITSRISIKO: Lokale Agent-API darf nicht auf {host} binden.",
        )
        return None

    if not _is_usable_token(token):
        log(
            "ERROR",
            "KONFIGURATION_ERFORDERLICH: Lokale Agent-API braucht einen echten Token.",
        )
        return None

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        log(
            "ERROR",
            f"Lokale Agent-API Port nicht verfügbar: {host}:{port} | {exc}",
        )
        return None
    finally:
        probe.close()

    server = LocalApiServer(
        config=config,
        host=host,
        port=port,
        token=token,
        log=log,
        run_morning=run_morning,
        stop_agent=stop_agent,
        brain=brain,
        tool_executor=tool_executor,
        speak_fn=speak_fn,
    )
    server.start()
    return server
