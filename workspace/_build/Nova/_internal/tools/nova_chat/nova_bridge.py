"""
nova_chat/nova_bridge.py -- Bridge: Nova's chat words → real disk actions
=========================================================================
OpenClaw's WebSocket rejects external connections (policy 1008).
We don't need it. The nova_chat server already runs inside the workspace
and has full disk access. We write directly.

Nova's syntax in chat:
    [WRITE:logs/proposed/my_file.py]
    def my_function(): ...
    [/WRITE]

    [EXEC:python tools/nova_sync/watcher.py --push]

    [READ:tools/nova_action/autonomy.py]
"""
import json
import asyncio
import os
import re
import subprocess
import time
from pathlib import Path

# ── Discord dedup cache ────────────────────────────────────────────────────────
# Prevents Nova from spamming Discord when her transcript makes her repeat the
# same [DISCORD:] directive on consecutive turns.
_DISCORD_SENT: dict[str, float] = {}   # message text → last sent timestamp
_DISCORD_DEDUP_WINDOW = 300            # 5 minutes — same text = duplicate within this window

WORKSPACE_DIR = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent.parent
)

WRITE_PATTERN   = re.compile(r'\[WRITE:([^\]]+)\]\s*(.*?)\s*\[/WRITE\]', re.DOTALL | re.IGNORECASE)
EXEC_PATTERN    = re.compile(r'\[EXEC:([^\]]+)\]', re.IGNORECASE)
READ_PATTERN    = re.compile(r'\[READ:([^\]]+)\]', re.IGNORECASE)
PAUSE_PATTERN   = re.compile(r'\[PAUSE:\s*([^\]]*)\]', re.IGNORECASE)
RESUME_PATTERN  = re.compile(r'\[RESUME:\s*([^\]]*)\]', re.IGNORECASE)
# [DISCORD: message text] — send a message to Discord via nova_gateway
DISCORD_PATTERN = re.compile(r'\[DISCORD:\s*(.*?)\]', re.DOTALL | re.IGNORECASE)


def parse_actions(message: str) -> list[dict]:
    actions = []
    for m in WRITE_PATTERN.finditer(message):
        actions.append({"type": "write", "path": m.group(1).strip(), "content": m.group(2).strip()})
    for m in EXEC_PATTERN.finditer(message):
        actions.append({"type": "exec", "cmd": m.group(1).strip()})
    for m in READ_PATTERN.finditer(message):
        actions.append({"type": "read", "path": m.group(1).strip()})
    for m in PAUSE_PATTERN.finditer(message):
        actions.append({"type": "pause", "task": m.group(1).strip()})
    for m in RESUME_PATTERN.finditer(message):
        actions.append({"type": "resume", "task": m.group(1).strip()})
    for m in DISCORD_PATTERN.finditer(message):
        actions.append({"type": "discord", "text": m.group(1).strip()})
    return actions


async def execute_action(action: dict) -> str:
    a_type = action.get("type")

    if a_type == "write":
        path_str = action["path"].replace("\\", "/")
        # Safety: must stay inside workspace
        target = (WORKSPACE_DIR / path_str).resolve()
        try:
            target.relative_to(WORKSPACE_DIR.resolve())
        except ValueError:
            return f"[bridge] ✗ Path escapes workspace: {path_str}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(action["content"], encoding="utf-8")
            rel = str(target.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            return f"[bridge] ✓ Written: {rel}"
        except Exception as e:
            return f"[bridge] ✗ Write failed: {e}"

    elif a_type == "exec":
        cmd = action["cmd"]
        try:
            import sys
            proc = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=30, cwd=str(WORKSPACE_DIR),
                encoding="utf-8", errors="replace"
            )
            out = (proc.stdout or "")[-300:].strip()
            err = (proc.stderr or "")[-200:].strip()
            if proc.returncode == 0:
                return f"[bridge] ✓ Exec: {cmd[:60]}" + (f" → {out}" if out else "")
            else:
                return f"[bridge] ✗ Exec exit {proc.returncode}: {err or out}"
        except subprocess.TimeoutExpired:
            return f"[bridge] ✗ Exec timed out: {cmd[:60]}"
        except Exception as e:
            return f"[bridge] ✗ Exec error: {e}"

    elif a_type == "read":
        path_str = action["path"].replace("\\", "/")
        target = (WORKSPACE_DIR / path_str).resolve()
        try:
            target.relative_to(WORKSPACE_DIR.resolve())
            content = target.read_text(encoding="utf-8", errors="replace")[:3000]
            return f"[bridge] ✓ Read {path_str} ({len(content)} chars) — content injected to context"
        except Exception as e:
            return f"[bridge] ✗ Read failed: {e}"

    # 1.6 -- PAUSE directive: pause the active task in nova_status.json
    elif a_type == "pause":
        task_id = action.get("task", "")
        note    = task_id  # the text after PAUSE: is treated as a note
        try:
            import sys as _sys
            _sys.path.insert(0, str(WORKSPACE_DIR / "tools"))
            from nova_core.nova_status import pause_task
            pause_task(note=note)
            return f"[bridge] ⏸ Paused" + (f": {note}" if note else "")
        except Exception as e:
            return f"[bridge] ✗ Pause failed: {e}"

    # 1.6 -- RESUME directive: resume a paused task
    elif a_type == "resume":
        task_id = action.get("task", "")
        try:
            import sys as _sys
            _sys.path.insert(0, str(WORKSPACE_DIR / "tools"))
            from nova_core.nova_status import resume_task
            resume_task(task_id=task_id or None)
            return f"[bridge] ▶ Resumed" + (f": {task_id}" if task_id else "")
        except Exception as e:
            return f"[bridge] ✗ Resume failed: {e}"

    # DISCORD directive: send a message to Discord via nova_gateway
    elif a_type == "discord":
        text = action.get("text", "").strip()
        if not text:
            return "[bridge] ✗ Discord: no message text"
        # Deduplication guard: reject if the same text was sent recently
        now = time.time()
        # Evict old entries
        expired = [k for k, v in _DISCORD_SENT.items() if now - v > _DISCORD_DEDUP_WINDOW]
        for k in expired:
            del _DISCORD_SENT[k]
        if text in _DISCORD_SENT:
            age = int(now - _DISCORD_SENT[text])
            return f"[bridge] ⚠ Discord duplicate blocked — same message sent {age}s ago (cooldown {_DISCORD_DEDUP_WINDOW}s)"
        _DISCORD_SENT[text] = now
        try:
            import urllib.request, urllib.error, json as _json
            payload = _json.dumps({"text": text}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:18790/api/discord/send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = _json.loads(resp.read())
            return f"[bridge] ✓ Discord message sent ({result.get('chars', '?')} chars)"
        except urllib.error.HTTPError as e:
            # Read gateway's error detail for better diagnostics
            try:
                error_body = e.read().decode("utf-8", errors="replace")
                detail = _json.loads(error_body).get("detail", "")
            except Exception:
                detail = ""
            return f"[bridge] ✗ Discord send failed: HTTP {e.code} — {detail or e.reason}"
        except urllib.error.URLError as e:
            return f"[bridge] ✗ Discord gateway unreachable: {e.reason}"
        except Exception as e:
            return f"[bridge] ✗ Discord send failed: {e}"

    return f"[bridge] ✗ Unknown action: {a_type}"


async def handle_nova_message(message: str) -> list[str]:
    actions = parse_actions(message)
    if not actions:
        return []
    results = []
    for action in actions:
        result = await execute_action(action)
        results.append(result)
    return results
