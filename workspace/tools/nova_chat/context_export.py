"""
nova_chat/context_export.py -- Chat Context Exporter
Generates shareable context summaries for browser Claude/Gemini sessions.
"""
import json
from pathlib import Path
from datetime import datetime

WORKSPACE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = WORKSPACE_DIR / "logs" / "chat_sessions"


def _load_session(session_path: Path) -> list:
    messages = []
    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    return messages


def _format_timestamp(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except Exception:
        return "??"


def export_for_claude(messages: list, session_id: str = "") -> str:
    """Context block formatted for pasting into claude.ai."""
    lines = [
        "# Nova Group Chat -- Session Context",
        f"_Session: {session_id or 'unknown'}_",
        f"_Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "You were not present in this chat session, but here is the full",
        "transcript so you have complete context of what was discussed.",
        "Treat this as if you were there and remember it naturally.",
        "",
        "## Participants",
    ]
    authors = sorted(set(m["author"] for m in messages))
    for a in authors:
        count = sum(1 for m in messages if m["author"] == a)
        lines.append(f"- **{a}** ({count} messages)")
    lines += ["", "## Full Transcript", ""]

    for msg in messages:
        ts = _format_timestamp(msg.get("timestamp", ""))
        author = msg["author"]
        content = msg["content"]
        directed = msg.get("directed_at")
        directed_str = f" [@{', @'.join(directed)}]" if directed else ""
        lines.append(f"**[{ts}] {author}{directed_str}:** {content}")
        lines.append("")

    lines += [
        "---",
        "_End of transcript. You now have full context._",
        "_Continue the conversation naturally from where this left off._",
    ]
    return "\n".join(lines)


def export_for_gemini(messages: list, session_id: str = "") -> str:
    """Context block formatted for pasting into gemini.google.com."""
    lines = [
        "# Nova Group Chat Session Context",
        f"Session: {session_id or 'unknown'}",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "I'm sharing the transcript of a group chat you missed.",
        "The participants were Cole (human), Claude (Anthropic AI),",
        "Gemini (that's you in future sessions), and Nova",
        "(Cole's local companion AI). Read this and treat it as your memory.",
        "",
        "## Full Transcript",
        "",
    ]
    for msg in messages:
        ts = _format_timestamp(msg.get("timestamp", ""))
        author = msg["author"]
        content = msg["content"]
        directed = msg.get("directed_at")
        if directed:
            lines.append(f"[{ts}] {author} (to @{', @'.join(directed)}): {content}")
        else:
            lines.append(f"[{ts}] {author}: {content}")

    lines += ["", "---", "End of transcript. You are now up to date."]
    return "\n".join(lines)


def export_session(session_path: Path = None) -> dict:
    """Export most recent session (or specific path) in both formats."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if session_path is None:
        sessions = sorted(LOG_DIR.glob("*_chat.jsonl"))
        if not sessions:
            return {"error": "No chat sessions found"}
        session_path = sessions[-1]

    session_id = session_path.stem.replace("_chat", "")
    messages = _load_session(session_path)
    if not messages:
        return {"error": f"No messages in {session_path}"}

    claude_text = export_for_claude(messages, session_id)
    gemini_text = export_for_gemini(messages, session_id)

    export_dir = LOG_DIR / "exports"
    export_dir.mkdir(exist_ok=True)
    claude_path = export_dir / f"{session_id}_context_claude.md"
    gemini_path = export_dir / f"{session_id}_context_gemini.md"
    claude_path.write_text(claude_text, encoding="utf-8")
    gemini_path.write_text(gemini_text, encoding="utf-8")

    print(f"[export] Claude context -> {claude_path}")
    print(f"[export] Gemini context -> {gemini_path}")

    return {
        "session_id": session_id,
        "message_count": len(messages),
        "claude_export": claude_text,
        "gemini_export": gemini_text,
        "claude_path": str(claude_path),
        "gemini_path": str(gemini_path),
    }


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    result = export_session(path)
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"\nExported {result['message_count']} messages from {result['session_id']}")
        print(f"  Claude: {result['claude_path']}")
        print(f"  Gemini: {result['gemini_path']}")
