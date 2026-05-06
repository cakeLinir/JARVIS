import os

import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv

from backend_client import JarvisBackendClient
from formatters import format_morning_log, format_status, shorten_for_discord


load_dotenv()


def get_allowed_guild_ids() -> list[int] | None:
    raw = os.getenv("JARVIS_ALLOWED_GUILD_ID", "").strip()

    if not raw:
        return None

    try:
        return [int(raw)]
    except ValueError:
        return None


def get_interaction_role_ids(interaction: nextcord.Interaction) -> list[str]:
    user = interaction.user

    roles = getattr(user, "roles", None)

    if not roles:
        return []

    result: list[str] = []

    for role in roles:
        role_id = getattr(role, "id", None)
        role_name = getattr(role, "name", "")

        if role_id and role_name != "@everyone":
            result.append(str(role_id))

    return result


class JarvisCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        backend_url = os.getenv("JARVIS_BACKEND_URL", "http://localhost:8080").strip()
        bridge_token = os.getenv("JARVIS_BOT_BRIDGE_TOKEN", "").strip()

        self.backend = JarvisBackendClient(
            backend_url=backend_url,
            token=bridge_token,
        )

    @nextcord.slash_command(
        name="jarvis_ping_backend",
        description="Prüft, ob das JARVIS-Backend erreichbar ist.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_ping_backend(self, interaction: nextcord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = self.backend.get_health()

            await interaction.followup.send(
                (
                    "**JARVIS Backend**\n"
                    f"Status: `{data.get('status')}`\n"
                    f"Service: `{data.get('service')}`\n"
                    f"Zeit: `{data.get('timestamp')}`"
                ),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"Backend nicht erreichbar: `{exc}`",
                ephemeral=True,
            )

    @nextcord.slash_command(
        name="jarvis_status",
        description="Zeigt den aktuellen JARVIS-Agent-Status.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_status(self, interaction: nextcord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = self.backend.get_agent_status()
            message = format_status(data)

            await interaction.followup.send(
                shorten_for_discord(message),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"JARVIS-Status konnte nicht gelesen werden: `{exc}`",
                ephemeral=True,
            )

    @nextcord.slash_command(
        name="jarvis_morning_log",
        description="Zeigt das letzte JARVIS-Morning-Log.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_morning_log(self, interaction: nextcord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = self.backend.get_morning_log()
            message = format_morning_log(data)

            await interaction.followup.send(
                shorten_for_discord(message),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"JARVIS-Morning-Log konnte nicht gelesen werden: `{exc}`",
                ephemeral=True,
            )

    @nextcord.slash_command(
        name="jarvis_start_morning",
        description="Startet die JARVIS-Morgenroutine nach Bestätigung.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_start_morning(
        self,
        interaction: nextcord.Interaction,
        confirm_code: str = nextcord.SlashOption(
            description="Zum Start exakt START eingeben.",
            required=False,
        ),
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if confirm_code != "START":
            await interaction.followup.send(
                (
                    "**Bestätigung erforderlich.**\n"
                    "Dieser Befehl startet lokale Programme auf deinem PC.\n\n"
                    "Führe den Befehl erneut aus mit:\n"
                    "`confirm_code: START`"
                ),
                ephemeral=True,
            )
            return

        try:
            command = self.backend.create_command(
                command_type="morning_routine",
                requested_by=str(interaction.user),
                discord_user_id=str(interaction.user.id),
                discord_role_ids=get_interaction_role_ids(interaction),
                payload={
                    "source": "discord",
                    "guildId": str(interaction.guild_id) if interaction.guild_id else None,
                    "channelId": str(interaction.channel_id) if interaction.channel_id else None,
                },
            )

            command_id = command.get("command", {}).get("id", "unbekannt")

            await interaction.followup.send(
                (
                    "**JARVIS Command erstellt.**\n"
                    f"Typ: `morning_routine`\n"
                    f"Command-ID: `{command_id}`\n\n"
                    "Der Local Agent führt den Befehl aus, sobald er online ist."
                ),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"Morning Routine konnte nicht angefordert werden: `{exc}`",
                ephemeral=True,
            )

    @nextcord.slash_command(
        name="jarvis_dev_news",
        description="Ruft den aktuellen Dev-News-Status vom Backend ab.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_dev_news(self, interaction: nextcord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = self.backend.get_dev_news()

            items = data.get("items", [])
            errors = data.get("errors", [])

            if not items:
                source_names = [source.get("name", "?") for source in data.get("sources", [])]
                source_text = "\n".join(f"- {item}" for item in source_names) if source_names else "Keine Quellen vorhanden."
                error_text = "\n".join(f"- {item}" for item in errors[:5]) if errors else "Keine Fehler gemeldet."
                message = (
                    "**JARVIS Dev-News**\n"
                    "Keine News-Einträge geladen.\n\n"
                    f"**Quellen:**\n{source_text}\n\n"
                    f"**Fehler:**\n{error_text}"
                )
            else:
                lines = [
                    "**JARVIS Dev-News**",
                    f"Stand: `{data.get('fetchedAt')}`",
                    ""
                ]

                for item in items[:5]:
                    lines.append(
                        (
                            f"- **{item.get('title', 'Ohne Titel')}**\n"
                            f"  Quelle: `{item.get('source')}` | Datum: `{item.get('date')}`\n"
                            f"  {item.get('link')}"
                        )
                    )

                if errors:
                    lines.append("\n**Quellenfehler:**")
                    lines.extend(f"- {item}" for item in errors[:3])

                message = "\n".join(lines)

            await interaction.followup.send(
                shorten_for_discord(message),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"Dev-News konnten nicht gelesen werden: `{exc}`",
                ephemeral=True,
            )

    @nextcord.slash_command(
        name="jarvis_commands",
        description="Zeigt die letzten JARVIS-Commands.",
        guild_ids=get_allowed_guild_ids(),
    )
    async def jarvis_commands(self, interaction: nextcord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = self.backend.get_recent_commands()
            commands = data.get("commands", [])

            if not commands:
                await interaction.followup.send(
                    "Keine Commands vorhanden.",
                    ephemeral=True,
                )
                return

            lines = ["**Letzte JARVIS Commands**"]

            for command in commands[:10]:
                lines.append(
                    (
                        f"- `{command.get('id')}` | "
                        f"`{command.get('type')}` | "
                        f"`{command.get('status')}` | "
                        f"{command.get('requestedBy')}"
                    )
                )

            await interaction.followup.send(
                shorten_for_discord("\n".join(lines)),
                ephemeral=True,
            )

        except Exception as exc:
            await interaction.followup.send(
                f"Commands konnten nicht gelesen werden: `{exc}`",
                ephemeral=True,
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(JarvisCog(bot))
