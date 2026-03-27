"""
nova_gateway/discord_client.py
================================
Discord bot integration using discord.py.

What this does (plain English):
  This is the "ears and mouth" of the gateway. It:
    - Connects to Discord using your bot token
    - Watches the channels you've allowlisted in nova_gateway.json
    - When you (or someone permitted) sends Nova a message, it fires
      the agent_loop to get her response
    - When the agent_loop produces a response, it sends it back to Discord
    - Handles DMs if enabled

  This replaces the discord.js integration inside OpenClaw entirely.

Requirements:
  pip install discord.py

Discord bot setup (if you haven't already):
  1. Go to https://discord.com/developers/applications
  2. Create application → Bot → copy token → paste in nova_gateway.json
  3. Enable "Message Content Intent" under Bot → Privileged Gateway Intents
  4. Invite bot to your server with at minimum: Read Messages, Send Messages,
     Read Message History permissions
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from .config import cfg

if TYPE_CHECKING:
    from .tool_executor import ToolExecutor

log = logging.getLogger(__name__)

# ── Try importing discord.py ─────────────────────────────────────────────────
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    log.warning(
        "discord.py not installed. Discord integration disabled. "
        "Install with: pip install discord.py"
    )


# ── Bot class ─────────────────────────────────────────────────────────────────

class NovaDiscordBot:
    """
    Wraps a discord.py Bot and connects it to our agent_loop.

    Usage (called by gateway.py):
        bot = NovaDiscordBot(executor)
        await bot.start()   # blocks until disconnected
    """

    def __init__(self, executor: "ToolExecutor"):
        self.executor     = executor
        self._bot         = None
        self._nova_status_summary: str = ""

    def update_nova_status(self, summary: str) -> None:
        """Called by gateway.py's status polling loop to keep summary fresh."""
        self._nova_status_summary = summary

    async def start(self) -> None:
        """Connect to Discord and start listening. Blocks until stopped."""
        if not DISCORD_AVAILABLE:
            log.error("discord.py not available — cannot start Discord bot.")
            return

        token = cfg.discord.get("token", "")
        if not token or token == "PASTE_BOT_TOKEN_HERE":
            log.error(
                "Discord token not configured in nova_gateway.json. "
                "Set discord.token and discord.enabled = true."
            )
            return

        intents = discord.Intents.default()
        intents.message_content = True   # required to read message text
        intents.members          = False  # we don't need member lists
        intents.presences        = False  # we don't need presence info

        self._bot = discord.Client(intents=intents)
        self._register_events()

        # Give tool_executor a way to send Discord messages
        self.executor.set_discord(
            send_fn=self._send_message,
            default_channel=self._get_default_channel(),
        )

        log.info("Starting Discord bot...")
        await self._bot.start(token)

    async def stop(self) -> None:
        """Gracefully disconnect."""
        if self._bot and not self._bot.is_closed():
            await self._bot.close()
            log.info("Discord bot disconnected.")

    # ── Event handlers ───────────────────────────────────────────────────────

    def _register_events(self) -> None:
        bot = self._bot

        @bot.event
        async def on_ready():
            log.info(
                "Discord bot ready: %s (ID: %s)",
                bot.user.name, bot.user.id,
            )
            log.info(
                "Watching %d channel(s): %s",
                len(cfg.discord.get("allowlist", [])),
                cfg.discord.get("allowlist", []),
            )

        @bot.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        @bot.event
        async def on_error(event: str, *args, **kwargs):
            log.error("Discord error in event '%s'", event, exc_info=True)

    async def _handle_message(self, message: discord.Message) -> None:
        """Route an incoming Discord message to the agent loop."""
        # Ignore messages from the bot itself
        if self._bot and message.author.id == self._bot.user.id:
            return

        is_dm      = isinstance(message.channel, discord.DMChannel)
        channel_id = message.channel.id

        # Check allowlist (skip for DMs if dm_enabled)
        if is_dm:
            if not cfg.discord.get("dm_enabled", True):
                return
        else:
            allowlist = cfg.discord.get("allowlist", [])
            if allowlist and channel_id not in allowlist:
                return   # channel not in allowlist, ignore

        # Check bot policy
        if message.author.bot and not cfg.discord.get("allow_bots", True):
            return

        author  = str(message.author.display_name)
        channel = message.channel.name if hasattr(message.channel, "name") else "DM"
        text    = message.content.strip()

        if not text:
            return   # empty message (e.g. image-only)

        log.info(
            "Discord trigger: #%s from %s: %s",
            channel, author, text[:80],
        )

        # Show typing indicator while Nova thinks
        async with message.channel.typing():
            try:
                from .agent_loop import run_agent
                result = await run_agent(
                    text=text,
                    source="discord",
                    author=author,
                    channel=channel,
                    channel_id=channel_id,
                    executor=self.executor,
                    nova_status_summary=self._nova_status_summary,
                )
            except Exception as e:
                log.error("Agent loop crashed: %s", e, exc_info=True)
                await message.channel.send(
                    f"⚠️ Nova encountered an error: `{type(e).__name__}: {e}`"
                )
                return

        # Send response
        if result.ok and result.text:
            await self._send_long_message(message.channel, result.text)
            log.info(
                "Replied to %s: %d chars, %d tool calls, %.1fs",
                author, len(result.text), result.tool_calls_made, result.duration_s,
            )
        elif not result.ok:
            await message.channel.send(
                f"⚠️ Nova error: `{result.error}`"
            )
        # If result.text is empty (Nova only called tools, no final text), stay silent

    # ── Sending helpers ──────────────────────────────────────────────────────

    async def _send_message(self, channel_id: int, text: str) -> None:
        """Send a message to a specific channel by ID. Used by tool_executor."""
        if not self._bot:
            raise RuntimeError("Bot not connected")
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(channel_id)
        await self._send_long_message(channel, text)

    async def _send_long_message(
        self,
        channel: discord.abc.Messageable,
        text: str,
        chunk_size: int = 1900,
    ) -> None:
        """
        Send a message, splitting into chunks if > 2000 chars (Discord limit).
        Tries to split on newlines to avoid cutting mid-word.
        """
        if len(text) <= chunk_size:
            await channel.send(text)
            return

        # Split into chunks
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= chunk_size:
                chunks.append(remaining)
                break
            # Find a newline to split on
            split_at = remaining.rfind("\n", 0, chunk_size)
            if split_at == -1:
                split_at = chunk_size
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")

        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.5)   # brief pause between chunks
            await channel.send(chunk)

    def _get_default_channel(self) -> Optional[int]:
        """Return the first allowlisted channel ID as the default."""
        allowlist = cfg.discord.get("allowlist", [])
        return allowlist[0] if allowlist else None


# ── Standalone runner (used by gateway.py) ────────────────────────────────────

async def run_discord_bot(executor: "ToolExecutor") -> None:
    """
    Create and run the Discord bot until cancelled.
    Called by gateway.py inside an asyncio task.
    """
    bot = NovaDiscordBot(executor)
    try:
        await bot.start()
    except asyncio.CancelledError:
        await bot.stop()
    except Exception as e:
        log.error("Discord bot crashed: %s", e, exc_info=True)
        raise


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    if not DISCORD_AVAILABLE:
        print("discord.py not installed. Run: pip install discord.py")
    elif not cfg.discord.get("enabled"):
        print("Discord not enabled in nova_gateway.json.")
        print("Set discord.enabled = true and fill in discord.token.")
    else:
        print("Starting Discord bot... (Ctrl+C to stop)")
        from .tool_executor import ToolExecutor
        executor = ToolExecutor()
        asyncio.run(run_discord_bot(executor))
