import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotBridgeConfig:
    nextcord_bot_token: str
    backend_url: str
    bot_bridge_token: str
    allowed_guild_id: int | None


def load_config() -> BotBridgeConfig:
    bot_bridge_root = Path(__file__).resolve().parents[1]
    env_path = bot_bridge_root / ".env"

    load_dotenv(dotenv_path=env_path, encoding="utf-8-sig", override=True)

    raw_guild_id = os.getenv("JARVIS_ALLOWED_GUILD_ID", "").strip()
    allowed_guild_id: int | None = None

    if raw_guild_id:
        try:
            allowed_guild_id = int(raw_guild_id)
        except ValueError:
            allowed_guild_id = None

    return BotBridgeConfig(
        nextcord_bot_token=os.getenv("NEXTCORD_BOT_TOKEN", "").strip(),
        backend_url=os.getenv("JARVIS_BACKEND_URL", "http://localhost:8080").strip(),
        bot_bridge_token=os.getenv("JARVIS_BOT_BRIDGE_TOKEN", "").strip(),
        allowed_guild_id=allowed_guild_id,
    )
