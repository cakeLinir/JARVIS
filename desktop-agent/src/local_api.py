import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


LogFn = Callable[[str, str], None]
ActionFn = Callable[[], None]
StopFn = Callable[[], None]


class LocalApiServer:
    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        log: LogFn,
        run_morning: ActionFn,
        stop_agent: StopFn,
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.log = log
        self.run_morning = run_morning
        self.stop_agent = stop_agent
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

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
                if not parent.token:
                    return True

                expected = f"Bearer {parent.token}"
                return self.headers.get("Authorization", "") == expected

            def _read_json_body(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}

                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                if not raw:
                    return {}

                return json.loads(raw)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._send_json(200, {"ok": True, "service": "jarvis-local-agent"})
                    return

                self._send_json(404, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized():
                    self._send_json(403, {"ok": False, "error": "invalid_local_api_token"})
                    return

                try:
                    body = self._read_json_body()
                except Exception as exc:
                    self._send_json(400, {"ok": False, "error": "invalid_json", "message": str(exc)})
                    return

                if self.path == "/actions/morning":
                    confirm = body.get("confirm")
                    if confirm != "START":
                        self._send_json(400, {"ok": False, "error": "confirmation_required"})
                        return

                    threading.Thread(target=parent.run_morning, daemon=True).start()
                    self._send_json(202, {"ok": True, "accepted": True, "action": "morning_routine"})
                    return

                if self.path == "/actions/stop":
                    parent.stop_agent()
                    self._send_json(202, {"ok": True, "accepted": True, "action": "stop"})
                    return

                self._send_json(404, {"ok": False, "error": "not_found"})

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.log("INFO", f"Lokale Agent-API gestartet: http://{self.host}:{self.port}")

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
) -> LocalApiServer | None:
    local_api_config = config.get("localApi", {})

    if not local_api_config.get("enabled", False):
        log("INFO", "Lokale Agent-API deaktiviert.")
        return None

    host = str(local_api_config.get("host", "127.0.0.1"))
    port = int(local_api_config.get("port", 8765))
    token = str(local_api_config.get("token", ""))

    server = LocalApiServer(
        host=host,
        port=port,
        token=token,
        log=log,
        run_morning=run_morning,
        stop_agent=stop_agent,
    )
    server.start()
    return server
