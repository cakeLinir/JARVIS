import nextcord
from nextcord.ext import commands

from config import load_config


config = load_config()

intents = nextcord.Intents.default()

bot = commands.Bot(
    command_prefix="!jarvis ",
    intents=intents,
)


@bot.event
async def on_ready() -> None:
    print(f"JARVIS Bot Bridge online als {bot.user}")


def main() -> None:
    if not config.nextcord_bot_token or config.nextcord_bot_token.startswith("CHANGE_ME"):
        raise RuntimeError(
            "NEXTCORD_BOT_TOKEN fehlt. Trage den Bot-Token in bot-bridge/.env ein."
        )

    bot.load_extension("cogs.jarvis_cog")
    bot.run(config.nextcord_bot_token)


if __name__ == "__main__":
    main()
