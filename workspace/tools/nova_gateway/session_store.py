"""
nova_gateway/session_store.py
==============================
JSONL v4 session writer, reader, and compaction engine.

What this does (plain English):
  Every conversation Nova has is saved as a text file where each line
  is one "event" (a message, a tool call, a session start, etc.).
  This module handles writing those files, reading them back, and
  "compacting" them when they get too long for Nova's memory window.

File location: workspace/sessions/YYYY-MM-DD/<uuid>.jsonl
Format: JSONL v4 (one JSON object per line, version field = 4)

Compaction: when the conversation history is > 85% of context_window,
  we ask Nova to summarize what happened, save the summary, and drop
  the old messages. This is the same thing OpenClaw did automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import cfg
from .context_builder import estimate_tokens

log = logging.getLogger(__name__)

# ── Record type constants ────────────────────────────────────────────────────
T_SESSION    = "session"
T_MESSAGE    = "message"
T_TOOL_CALL  = "tool_call"
T_COMPACTION = "compaction"


# ── Session class ─────────────────────────────────────────────────────────────

class Session:
    """
    Represents one Nova agent session (one conversation thread).

    Usage:
        session = Session.new(trigger="discord")
        session.add_message("user", "Hey Nova, how are you?")
        session.add_message("assistant", "I'm doing great!")
        session.save()

    Or load an existing one:
        session = Session.load(session_id)
    """

    def __init__(
        self,
        session_id: str,
        path: Path,
        records: list[dict],
        trigger: str = "discord",
    ):
        self.id       = session_id
        self.path     = path
        self.records  = records   # full history, all record types
        self.trigger  = trigger

    # ── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def new(cls, trigger: str = "discord") -> "Session":
        """Create a fresh session and write the session header record."""
        session_id = str(uuid.uuid4())
        today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sessions_dir = cfg.sessions_dir / today
        sessions_dir.mkdir(parents=True, exist_ok=True)
        path = sessions_dir / f"{session_id}.jsonl"

        header = {
            "type":      T_SESSION,
            "version":   4,
            "id":        session_id,
            "trigger":   trigger,
            "timestamp": _now_iso(),
            "workspace": str(cfg.workspace),
        }
        _append_record(path, header)

        session = cls(session_id, path, [header], trigger)
        log.info("New session %s (trigger=%s) → %s", session_id[:8], trigger, path.name)
        return session

    @classmethod
    def load(cls, session_id: str) -> Optional["Session"]:
        """
        Load an existing session by ID.
        Searches all date subdirectories under sessions_dir.
        Returns None if not found.
        """
        for jsonl in cfg.sessions_dir.rglob(f"{session_id}.jsonl"):
            records = _read_all_records(jsonl)
            trigger = next(
                (r.get("trigger", "discord") for r in records if r.get("type") == T_SESSION),
                "discord"
            )
            return cls(session_id, jsonl, records, trigger)
        log.warning("Session not found: %s", session_id)
        return None

    @classmethod
    def load_latest(cls) -> Optional["Session"]:
        """Load the most recently modified session (useful for resume)."""
        all_files = sorted(
            cfg.sessions_dir.rglob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not all_files:
            return None
        records = _read_all_records(all_files[0])
        session_id = next(
            (r.get("id") for r in records if r.get("type") == T_SESSION),
            str(uuid.uuid4())
        )
        return cls(session_id, all_files[0], records)

    # ── Writing ──────────────────────────────────────────────────────────────

    def add_message(self, role: str, content: Any, model: str = "", usage: dict = None) -> None:
        """
        Append a conversation message to the session.

        role:    "user" | "assistant"
        content: str or list of content blocks (text + tool_calls)
        model:   which Ollama model responded (for assistant messages)
        usage:   token usage dict from Ollama response
        """
        record = {
            "type":      T_MESSAGE,
            "role":      role,
            "content":   content,
            "timestamp": _now_iso(),
        }
        if model:
            record["model"] = model
        if usage:
            record["usage"] = usage

        self.records.append(record)
        _append_record(self.path, record)

    def add_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        duration_ms: int = 0,
        error: bool = False,
    ) -> None:
        """Append a tool execution record (call + result together)."""
        record = {
            "type":        T_TOOL_CALL,
            "name":        tool_name,
            "arguments":   arguments,
            "result":      result[:4096],   # cap at 4KB to avoid bloat
            "duration_ms": duration_ms,
            "error":       error,
            "timestamp":   _now_iso(),
        }
        self.records.append(record)
        _append_record(self.path, record)

    def add_compaction(self, summary: str, tokens_before: int) -> None:
        """Append a compaction record and truncate in-memory history."""
        record = {
            "type":          T_COMPACTION,
            "summary":       summary,
            "tokens_before": tokens_before,
            "timestamp":     _now_iso(),
        }
        # In the JSONL file, compaction is just another record.
        # In memory, we drop all old messages but keep this record
        # so the next prompt build can use the summary.
        _append_record(self.path, record)

        # Reset in-memory records: keep session header + compaction only
        header_records = [r for r in self.records if r.get("type") == T_SESSION]
        self.records = header_records + [record]
        log.info(
            "Session %s compacted: %d tokens → summary (%d chars)",
            self.id[:8], tokens_before, len(summary),
        )

    # ── Reading / building LLM messages ─────────────────────────────────────

    def build_messages(self) -> list[dict]:
        """
        Convert session records into the message list format Ollama expects.

        Returns a list of {"role": ..., "content": ...} dicts.
        Compaction summaries are injected as a system message.
        Tool call records are formatted as assistant + user turn pairs.
        """
        messages: list[dict] = []

        for r in self.records:
            rtype = r.get("type")

            if rtype == T_MESSAGE:
                messages.append({"role": r["role"], "content": r["content"]})

            elif rtype == T_COMPACTION:
                # Insert the summary as a system-level reminder
                messages.append({
                    "role": "system",
                    "content": (
                        "## Session Summary (earlier context was compacted)\n\n"
                        + r["summary"]
                    ),
                })

            elif rtype == T_TOOL_CALL:
                # Tool results come back as a user turn so the assistant
                # can see what happened
                status = "ERROR" if r.get("error") else "OK"
                messages.append({
                    "role": "user",
                    "content": (
                        f"[Tool result: {r['name']} | {status}]\n"
                        f"{r['result']}"
                    ),
                })

        return messages

    def token_estimate(self) -> int:
        """Rough token count of the current in-memory conversation."""
        total = 0
        for msg in self.build_messages():
            c = msg.get("content", "")
            if isinstance(c, str):
                total += estimate_tokens(c)
            elif isinstance(c, list):
                for block in c:
                    if isinstance(block, dict):
                        total += estimate_tokens(str(block))
        return total

    def needs_compaction(self) -> bool:
        """Return True if token count exceeds the compaction threshold."""
        ctx  = cfg.ollama["context_window"]
        frac = cfg.sessions["compact_at_frac"]
        used = self.token_estimate()
        if used > ctx * frac:
            log.info(
                "Session %s needs compaction: ~%d tokens (%.0f%% of %d)",
                self.id[:8], used, 100 * used / ctx, ctx,
            )
            return True
        return False


# ── Session listing ──────────────────────────────────────────────────────────

def list_sessions(limit: int = 50) -> list[dict]:
    """
    Return metadata for recent sessions (newest first).
    Used by nova_chat's log viewer API.
    """
    results = []
    for jsonl in sorted(
        cfg.sessions_dir.rglob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]:
        try:
            records = _read_all_records(jsonl)
            header  = next((r for r in records if r.get("type") == T_SESSION), {})
            msg_count = sum(1 for r in records if r.get("type") == T_MESSAGE)
            results.append({
                "id":        header.get("id", jsonl.stem),
                "trigger":   header.get("trigger", "?"),
                "timestamp": header.get("timestamp", ""),
                "messages":  msg_count,
                "path":      str(jsonl),
                "size_kb":   jsonl.stat().st_size // 1024,
            })
        except Exception as e:
            log.warning("Could not parse session %s: %s", jsonl.name, e)
    return results


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_record(path: Path, record: dict) -> None:
    """Append one JSON record to a JSONL file (atomic-safe: one write call)."""
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def _read_all_records(path: Path) -> list[dict]:
    """Read all records from a JSONL file, skipping malformed lines."""
    records = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("%s line %d: bad JSON, skipping", path.name, lineno)
    except OSError as e:
        log.error("Cannot read %s: %s", path, e)
    return records


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    s = Session.new(trigger="test")
    s.add_message("user", "Hello Nova!")
    s.add_message("assistant", "Hey Cole, what's up?")
    s.add_tool_call("exec", {"command": "echo hi"}, "hi", duration_ms=12)
    print(f"Session ID:     {s.id}")
    print(f"Session file:   {s.path}")
    print(f"Token estimate: {s.token_estimate()}")
    print(f"Needs compact:  {s.needs_compaction()}")
    print(f"Messages:")
    for m in s.build_messages():
        print(f"  [{m['role']}] {str(m['content'])[:80]}")
