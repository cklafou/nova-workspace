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


def build_system_prompt(
    heartbeat: bool = False,
    extra_context: Optional[str] = None,
) -> str:
    """
    Build and return Nova's full system prompt string.

    Args:
        heartbeat:     If True, include HEARTBEAT.md (only for cron triggers).
        extra_context: Optional additional text appended at the end (e.g.
                       nova_status.json summary from server.py polling).

    Returns:
        A single string ready to be sent as the "system" role message to Ollama.
    """
    sections: list[str] = [_SYSTEM_HEADER]
    inject_paths = cfg.inject_files(heartbeat=heartbeat)

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

    token_estimate = len(prompt) // 4   # rough: 1 token ≈ 4 chars
    log.debug(
        "System prompt built: %d chars (~%d tokens) from %d files",
        len(prompt), token_estimate, len(inject_paths),
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
