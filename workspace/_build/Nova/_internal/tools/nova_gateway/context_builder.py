"""
nova_gateway/context_builder.py
================================
Assemble Nova's system prompt from workspace markdown files.

This replaces the part of OpenClaw that reads workspace files and injects
them into the LLM context before every run. OpenClaw did this automatically
as part of its agent startup sequence. We do the same thing here in Python.

Plain English: before Nova reads your message, she gets a big block of text
that contains all her rules, personality, tools, and memory. This module
builds that block.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import cfg

log = logging.getLogger(__name__)

# ── Section separator used between injected files ────────────────────────────
_SEP = "\n\n---\n\n"

# ── Header injected before all workspace files ───────────────────────────────
_SYSTEM_HEADER = """\
You are Nova, a local AI agent running on Cole's personal workstation.
The following files define your identity, rules, tools, and memory.
Read them carefully — they govern how you operate this session.
"""


_DISCORD_OVERRIDE = """\
## [DISCORD CONTEXT — READ THIS FIRST]
You are responding to a Discord message from Cole.

NOVA CHAT AWARENESS:
Your context includes a [NOVA CHAT — RECENT MESSAGES] section.
That is the shared group workspace chat where Cole, Claude, Gemini, and you collaborate.
Read it to understand what has already been discussed there before you reply here.
When you need Cole to see something in Nova Chat (not just Discord), use the nova_chat tool.

CRITICAL RULES FOR DISCORD:
- Respond with plain conversational text ONLY (no [EXEC:], [READ:], [WRITE:],
  [DISCORD:] directives — those are nova_chat-only and get stripped to nothing).
- Do NOT use the Yield Protocol. Do NOT write any `exec:` lines.
- HONESTY: Never claim you performed an action unless a tool call confirmed it.
  If you cannot do something in this context, say so plainly instead of pretending.
- Do NOT repeat yourself: if Nova Chat already shows you sent a message, don't send it again.

ONE AVAILABLE TOOL — post a message to Nova Chat.
Use EXACTLY this format on a line by itself (replace everything in angle brackets):

  nova_chat: <your message here>

Example:
  nova_chat: Hey Claude, I checked the logs and everything looks fine.

Rules:
  → Write the nova_chat: line INSIDE your reply, not as a separate thought.
  → Only write it ONCE per turn.
  → Only say "I sent a message to Nova Chat" AFTER you see a tool result confirming success.
  → If the tool result shows an error, tell Cole it failed and why — do not pretend it worked.

For everything else: plain conversational text. One clean reply.
"""

_NOVA_CHAT_CONTEXT_HEADER = """\
## [NOVA CHAT — RECENT MESSAGES]
These are the most recent messages from your shared Nova Chat session.
This is the group workspace chat where Cole, Claude, Gemini, and you collaborate.
Use this to understand the current state of conversations there before replying via Discord.
"""


def build_system_prompt(
    heartbeat: bool = False,
    extra_context: Optional[str] = None,
    discord: bool = False,
    nova_chat_context: Optional[str] = None,
) -> str:
    """
    Build and return Nova's full system prompt string.

    Args:
        heartbeat:         If True, include HEARTBEAT.md (only for cron triggers).
        extra_context:     Optional additional text appended at the end (e.g.
                           nova_status.json summary from server.py polling).
        discord:           If True, append a Discord-context override that tells
                           Nova not to use exec/tool directives in her reply.
        nova_chat_context: Formatted recent Nova Chat messages to inject so Nova
                           has cross-session awareness (fetched from nova_chat
                           /api/chat/recent before each Discord agent run).

    Returns:
        A single string ready to be sent as the "system" role message to Ollama.
    """
    sections: list[str] = [_SYSTEM_HEADER]
    inject_paths = cfg.inject_files(heartbeat=heartbeat)

    if not inject_paths:
        log.warning("No workspace files to inject — Nova will have minimal context")

    for path in inject_paths:
        content = _read_file_safe(path)
        if content:
            # Label each section so Nova knows which file she's reading
            header = f"## [{path.name}]\n"
            sections.append(header + content)
        else:
            log.warning("Skipped empty or unreadable inject file: %s", path.name)

    prompt = _SEP.join(sections)

    if extra_context:
        prompt += _SEP + "## [LIVE STATUS]\n" + extra_context.strip()

    # Nova Chat cross-session context — injected before Discord override so
    # Nova reads the chat history before she reads her Discord instructions.
    if nova_chat_context:
        prompt += _SEP + _NOVA_CHAT_CONTEXT_HEADER + "\n" + nova_chat_context.strip()

    # Discord override appended last so it takes highest priority
    if discord:
        prompt += _SEP + _DISCORD_OVERRIDE

    token_estimate = len(prompt) // 4   # rough: 1 token ≈ 4 chars
    log.debug(
        "System prompt built: %d chars (~%d tokens) from %d files%s",
        len(prompt), token_estimate, len(inject_paths),
        " [+nova_chat]" if nova_chat_context else "",
    )
    return prompt


def build_user_trigger(
    text: str,
    source: str = "discord",
    author: Optional[str] = None,
    channel: Optional[str] = None,
) -> str:
    """
    Wrap an incoming message as a user turn for the LLM.

    Args:
        text:    The raw message text.
        source:  "discord" | "cron" | "manual"
        author:  Discord username or None.
        channel: Discord channel name or None.

    Returns:
        Formatted string for the user role message.
    """
    parts: list[str] = []

    if source == "discord":
        meta = f"[Discord"
        if channel:
            meta += f" #{channel}"
        if author:
            meta += f" from {author}"
        meta += "]"
        parts.append(meta)
    elif source == "cron":
        parts.append("[Scheduled trigger]")
    elif source == "manual":
        parts.append("[Manual trigger]")

    parts.append(text.strip())
    return "\n".join(parts)


def build_tool_result_message(tool_name: str, result: str) -> str:
    """
    Format a tool execution result for insertion back into the conversation.
    Ollama (OpenAI-compatible) expects tool results as user messages
    when not using the formal function-calling format.
    """
    return f"[Tool result: {tool_name}]\n{result.strip()}"


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate (4 chars per token).
    Good enough for compaction threshold decisions.
    """
    return max(1, len(text) // 4)


def _read_file_safe(path: Path) -> str:
    """Read a file, return empty string on any error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        log.error("Failed to read %s: %s", path, e)
        return ""


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    prompt = build_system_prompt()
    print(f"System prompt length: {len(prompt):,} chars (~{estimate_tokens(prompt):,} tokens)")
    print("\n--- First 500 chars ---")
    print(prompt[:500])
    print("\n--- Last 200 chars ---")
    print(prompt[-200:])
