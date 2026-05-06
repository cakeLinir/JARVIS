import json
import urllib.error
import urllib.request
from typing import Any


class JarvisBackendClient:
    def __init__(self, backend_url: str, token: str) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.token = token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def get_json(self, endpoint: str, timeout_seconds: int = 8) -> dict[str, Any]:
        if not self.backend_url:
            raise RuntimeError("Backend-URL fehlt.")

        if not self.token:
            raise RuntimeError("Bot-Bridge-Token fehlt.")

        url = self.backend_url + endpoint

        request = urllib.request.Request(
            url=url,
            method="GET",
            headers=self._auth_headers(),
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw)

        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend HTTP {exc.code}: {raw}") from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(f"Backend nicht erreichbar: {exc.reason}") from exc

    def post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: int = 8,
    ) -> dict[str, Any]:
        if not self.backend_url:
            raise RuntimeError("Backend-URL fehlt.")

        if not self.token:
            raise RuntimeError("Bot-Bridge-Token fehlt.")

        url = self.backend_url + endpoint
        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                **self._auth_headers(),
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw)

        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend HTTP {exc.code}: {raw}") from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(f"Backend nicht erreichbar: {exc.reason}") from exc

    def get_json_without_auth(self, endpoint: str, timeout_seconds: int = 8) -> dict[str, Any]:
        url = self.backend_url + endpoint

        request = urllib.request.Request(
            url=url,
            method="GET",
            headers={
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw)

        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend HTTP {exc.code}: {raw}") from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(f"Backend nicht erreichbar: {exc.reason}") from exc

    def get_agent_status(self) -> dict[str, Any]:
        return self.get_json("/api/agent/status")

    def get_morning_log(self) -> dict[str, Any]:
        return self.get_json("/api/agent/morning-log")

    def get_recent_commands(self) -> dict[str, Any]:
        return self.get_json("/api/commands/recent")

    def get_health(self) -> dict[str, Any]:
        return self.get_json_without_auth("/api/health")

    def get_dev_news(self) -> dict[str, Any]:
        return self.get_json_without_auth("/api/news/dev")

    def create_command(
        self,
        command_type: str,
        requested_by: str,
        discord_user_id: str | None = None,
        discord_role_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/api/commands",
            {
                "type": command_type,
                "requestedBy": requested_by,
                "discordUserId": discord_user_id,
                "discordRoleIds": discord_role_ids or [],
                "payload": payload or {},
            },
        )
