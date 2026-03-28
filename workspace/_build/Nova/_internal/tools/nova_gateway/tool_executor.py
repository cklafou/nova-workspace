"""
nova_gateway/tool_executor.py
==============================
Execute Nova's tool calls safely.

What this does (plain English):
  When Nova's LLM output includes a tool call (like "run this command"
  or "read this file"), this module intercepts it, does the actual work,
  and returns the result as a string. It's the bridge between Nova's
  intentions and real-world actions.

Tools supported:
  exec    — run a shell command (Nova's most-used tool)
  read    — read a file from the workspace
  message — send a Discord message (routed through discord_client)

Tools intentionally NOT supported (dropped from OpenClaw):
  write         — use [WRITE:] directives via nova_bridge instead (safer)
  session_status — use nova_status.py instead
  process        — not needed in our loop model
  memory_search  — use journal.py instead

Tool call format (what Ollama sends back):
  The LLM produces tool calls in OpenAI function-calling format:
  {
    "name": "exec",
    "arguments": {"command": "python tools/nova_rules.py"}
  }
  This module takes that dict and does the work.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .config import cfg

log = logging.getLogger(__name__)

# ── Type alias for the discord send function ─────────────────────────────────
# We pass this in from discord_client to avoid circular imports.
# Signature: async (channel_id: int, text: str) -> None
DiscordSendFn = Callable[[int, str], Any]

# ── Tool result when something goes wrong ────────────────────────────────────
_ERROR_PREFIX = "[ERROR] "


# ── Main dispatcher ──────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Dispatches tool calls to the correct handler.

    Usage:
        executor = ToolExecutor(discord_send_fn=my_async_send)
        result, error = await executor.run("exec", {"command": "echo hello"})
    """

    def __init__(self, discord_send: Optional[DiscordSendFn] = None):
        """
        discord_send: async function (channel_id, text) → None
                      Injected by discord_client at startup.
                      If None, the 'message' tool will return an error.
        """
        self._discord_send = discord_send
        self._default_channel: Optional[int] = None   # set by discord_client

        # Dispatch table: tool name → async handler
        self._handlers: dict[str, Callable] = {
            "exec":      self._exec,
            "read":      self._read,
            "message":   self._message,
            "nova_chat": self._nova_chat,   # post a message into nova_chat group chat
        }

    def set_discord(self, send_fn: DiscordSendFn, default_channel: int) -> None:
        """Called by discord_client after bot connects."""
        self._discord_send   = send_fn
        self._default_channel = default_channel

    async def run(
        self,
        tool_name: str,
        arguments: dict,
    ) -> tuple[str, bool]:
        """
        Execute a tool call.

        Returns: (result_text, is_error)
          result_text — string to send back to the LLM
          is_error    — True if the tool call failed
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            msg = (
                f"{_ERROR_PREFIX}Unknown tool '{tool_name}'. "
                f"Available tools: {', '.join(self._handlers)}"
            )
            log.warning("Unknown tool requested: %s", tool_name)
            return msg, True

        t0 = time.monotonic()
        try:
            result = await handler(arguments)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            log.debug("Tool %s completed in %dms", tool_name, elapsed_ms)
            return result, False
        except Exception as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            log.error("Tool %s raised exception after %dms: %s", tool_name, elapsed_ms, e, exc_info=True)
            return f"{_ERROR_PREFIX}{type(e).__name__}: {e}", True

    # ── exec ─────────────────────────────────────────────────────────────────

    async def _exec(self, args: dict) -> str:
        """
        Run a shell command.

        Arguments:
          command (str, required) — the command to run
          cwd     (str, optional) — working directory (default: workspace root)
          timeout (int, optional) — seconds before killing (default: from config)

        Returns the stdout + stderr combined, or an error message.
        """
        command = args.get("command", "").strip()
        if not command:
            return f"{_ERROR_PREFIX}exec requires a 'command' argument."

        cwd     = args.get("cwd") or cfg.tools.get("exec_cwd") or str(cfg.workspace)
        timeout = int(args.get("timeout", cfg.tools["exec_timeout_s"]))

        log.info("exec: %s (cwd=%s, timeout=%ds)", command[:120], cwd, timeout)

        # Run in thread pool to avoid blocking the event loop
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _run_subprocess(command, cwd, timeout),
        )
        return result

    # ── read ─────────────────────────────────────────────────────────────────

    async def _read(self, args: dict) -> str:
        """
        Read a file.

        Arguments:
          path (str, required) — file path, relative to workspace or absolute

        Returns file contents (truncated to read_max_bytes if large).
        Refuses to read outside workspace for security.
        """
        raw_path = args.get("path", "").strip()
        if not raw_path:
            return f"{_ERROR_PREFIX}read requires a 'path' argument."

        # Resolve path — relative paths are relative to workspace
        p = Path(raw_path)
        if not p.is_absolute():
            p = cfg.workspace / p
        p = p.resolve()

        # Security: must stay inside workspace
        try:
            p.relative_to(cfg.workspace.resolve())
        except ValueError:
            log.warning("read: path escape attempt blocked: %s", raw_path)
            return f"{_ERROR_PREFIX}Path is outside workspace: {raw_path}"

        if not p.exists():
            return f"{_ERROR_PREFIX}File not found: {raw_path}"
        if not p.is_file():
            return f"{_ERROR_PREFIX}Not a file: {raw_path}"

        max_bytes = cfg.tools["read_max_bytes"]
        try:
            content = p.read_bytes()
            if len(content) > max_bytes:
                text = content[:max_bytes].decode("utf-8", errors="replace")
                return text + f"\n\n[...truncated at {max_bytes} bytes]"
            return content.decode("utf-8", errors="replace")
        except OSError as e:
            return f"{_ERROR_PREFIX}Cannot read {raw_path}: {e}"

    # ── message ──────────────────────────────────────────────────────────────

    async def _message(self, args: dict) -> str:
        """
        Send a Discord message.

        Arguments:
          text       (str, required)  — message to send
          channel_id (int, optional)  — target channel (default: triggering channel)

        Returns confirmation or error.
        """
        if self._discord_send is None:
            return f"{_ERROR_PREFIX}Discord not connected — cannot send message."

        text = args.get("text", args.get("message", "")).strip()
        if not text:
            return f"{_ERROR_PREFIX}message requires a 'text' argument."

        channel_id = int(args.get("channel_id", self._default_channel or 0))
        if not channel_id:
            return f"{_ERROR_PREFIX}No channel_id provided and no default channel set."

        try:
            await self._discord_send(channel_id, text)
            log.info("message: sent %d chars to channel %d", len(text), channel_id)
            return f"Message sent to channel {channel_id} ({len(text)} chars)."
        except Exception as e:
            return f"{_ERROR_PREFIX}Discord send failed: {e}"

    async def _nova_chat(self, args: dict) -> str:
        """
        Post a message into the Nova Chat group chat session.

        Arguments:
          content (str, required) — message text to post
          author  (str, optional) — sender name shown in chat (default: "Nova")

        This calls nova_chat's /api/inject_message endpoint on port 8765.
        Only works when nova_chat server is running.
        """
        content = args.get("content", args.get("text", args.get("message", ""))).strip()
        if not content:
            return f"{_ERROR_PREFIX}nova_chat requires a 'content' argument."

        author = args.get("author", "Nova").strip() or "Nova"

        try:
            import urllib.request as _req
            import json as _json
            payload = _json.dumps({"author": author, "content": content}).encode("utf-8")
            request = _req.Request(
                "http://127.0.0.1:8765/api/inject_message",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _req.urlopen(request, timeout=5) as resp:
                result = _json.loads(resp.read())
            log.info("nova_chat: injected %d chars as %s", len(content), author)
            return f"Message posted to Nova Chat ({len(content)} chars, id={result.get('id', '?')})."
        except Exception as e:
            return f"{_ERROR_PREFIX}nova_chat inject failed: {e}"


# ── Subprocess helper (runs in thread pool) ───────────────────────────────────

def _run_subprocess(command: str, cwd: str, timeout: int) -> str:
    """
    Run command in a subprocess. Captures stdout + stderr combined.
    Returns output string. On timeout or error, returns error message.
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = ""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr:
            output += proc.stderr
        if proc.returncode != 0:
            output += f"\n[Exit code: {proc.returncode}]"
        return output.strip() or "(no output)"

    except subprocess.TimeoutExpired:
        return f"{_ERROR_PREFIX}Command timed out after {timeout}s: {command[:80]}"
    except Exception as e:
        return f"{_ERROR_PREFIX}subprocess error: {e}"


# ── Parse tool calls from Ollama response ────────────────────────────────────

def parse_tool_calls(response: dict) -> list[dict]:
    """
    Extract tool calls from an Ollama /v1/chat/completions response.

    Ollama can return tool calls in two ways:
      1. Standard OpenAI format: response["choices"][0]["message"]["tool_calls"]
      2. Text-based format: tool calls embedded in content as JSON blocks

    We handle format 1 here. Format 2 (text) is handled by parse_text_directives().

    Returns list of {"name": str, "arguments": dict} dicts.
    """
    calls = []
    try:
        message = response["choices"][0]["message"]
        raw_calls = message.get("tool_calls") or []
        for tc in raw_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            # Arguments may be a string (JSON) or already a dict
            args = func.get("arguments", {})
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            if name:
                calls.append({"name": name, "arguments": args})
    except (KeyError, IndexError, TypeError):
        pass
    return calls


def _extract_json_objects(text: str) -> list[dict]:
    """
    Extract all top-level JSON objects from arbitrary text using a
    balanced-brace parser. Handles multi-line and nested objects.
    Returns a list of successfully parsed dicts.
    """
    import json as _json
    results = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != '{':
            i += 1
            continue
        # Walk forward counting braces to find the matching close
        depth       = 0
        in_string   = False
        escape_next = False
        j = i
        while j < n:
            c = text[j]
            if escape_next:
                escape_next = False
            elif c == '\\' and in_string:
                escape_next = True
            elif c == '"':
                in_string = not in_string
            elif not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = _json.loads(text[i:j + 1])
                            if isinstance(obj, dict):
                                results.append(obj)
                        except Exception:
                            pass
                        i = j
                        break
            j += 1
        i += 1
    return results


def parse_text_directives(text: str) -> list[dict]:
    """
    Parse tool directives from Nova's text output.  Handles three forms:

      Bracketed:    [EXEC: command]  /  [READ: path]
      Bare line:    exec: command    (TOOLS.md Yield Protocol)
      Simple line:  nova_chat: message text here
      JSON block:   {"tool": "nova_chat", "arguments": {"content": "...", "author": "Nova"}}
                    (multi-line or single-line; any registered tool name)

    Returns list of {"name": str, "arguments": dict}.
    These are in addition to any formal tool_calls.

    Note: Regex patterns use non-greedy matching to prevent catastrophic
    backtracking on very long input.
    """
    import re
    calls = []

    # ── Bracketed form: [EXEC: ...], [READ: ...] ─────────────────────────────
    exec_re = re.compile(r'\[EXEC:\s*(.*?)\]', re.IGNORECASE | re.DOTALL)
    read_re = re.compile(r'\[READ:\s*(.*?)\]', re.IGNORECASE | re.DOTALL)

    for m in exec_re.finditer(text):
        calls.append({"name": "exec", "arguments": {"command": m.group(1).strip()}})
    for m in read_re.finditer(text):
        calls.append({"name": "read", "arguments": {"path": m.group(1).strip()}})

    # ── Bare line forms (only if no bracketed calls found) ───────────────────
    if not calls:
        # exec: command  (TOOLS.md Yield Protocol)
        bare_exec_re = re.compile(r'(?m)^exec:\s*(.+)$', re.IGNORECASE)
        for m in bare_exec_re.finditer(text):
            calls.append({"name": "exec", "arguments": {"command": m.group(1).strip()}})

        # nova_chat: message text  (simple Discord→NovacChat directive)
        nova_chat_re = re.compile(r'(?m)^nova_chat:\s*(.+)$', re.IGNORECASE)
        for m in nova_chat_re.finditer(text):
            calls.append({"name": "nova_chat", "arguments": {"content": m.group(1).strip(), "author": "Nova"}})

    # ── JSON block form: {"tool": "...", "arguments": {...}} ─────────────────
    # Nova may generate formal-looking JSON tool calls as plain text.
    # Extract all top-level JSON objects and look for tool+arguments shape.
    seen_tools: set[str] = {c["name"] for c in calls}
    for obj in _extract_json_objects(text):
        tool_name = obj.get("tool", "")
        tool_args = obj.get("arguments", obj.get("args", {}))
        if tool_name and isinstance(tool_args, dict) and tool_name not in seen_tools:
            calls.append({"name": tool_name, "arguments": tool_args})
            seen_tools.add(tool_name)

    return calls


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio, logging
    logging.basicConfig(level=logging.DEBUG)

    executor = ToolExecutor()

    async def test():
        result, err = await executor.run("exec", {"command": "echo Hello from nova_gateway"})
        print(f"exec result (error={err}):\n  {result}")

        result, err = await executor.run("read", {"path": "AGENTS.md"})
        print(f"read result (error={err}): {len(result)} chars")

        result, err = await executor.run("unknown_tool", {})
        print(f"unknown tool (error={err}): {result}")

    asyncio.run(test())
