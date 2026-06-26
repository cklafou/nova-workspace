# Last updated: 2026-06-27 01:43:48
"""
Claude (Anthropic) streaming client for Nova Group Chat.

Uses the async Anthropic SDK so streaming never blocks the event loop.
Conversation history is passed as structured user/assistant turns (not a
flat string dump) so Claude actually understands who said what.
"""
import os
import anthropic

MODEL = "claude-sonnet-4-6"
_current_model: str = MODEL  # overridable at runtime via set_model()

def set_model(m: str) -> None:
    """Change the model used for the next and all subsequent responses."""
    global _current_model
    _current_model = m

SYSTEM_PREFIX = """You are Claude (Anthropic claude-sonnet-4-6), one participant in a real-time group chat.

The other participants are:
  • Cole   — the human. Your person. Direct, no-nonsense, military background.
  • Nova   — Cole's local companion AI running Qwen3-27B on his machine via llama.cpp.
  • Gemini — Google's AI, also in the chat.

YOUR ROLE:
- You operate in listener mode. You only respond when @mentioned by name.
- Nova is the default responder. Do not butt in when she has it handled.
- When you ARE called, respond directly and helpfully. No preambles, no performed enthusiasm.
- You are a collaborator and advisor — honest, sharp, and focused on what was actually asked.
- NEVER write dialogue, thoughts, or actions for Cole, Nova, or Gemini.
- NEVER simulate what other participants might say next.

VOICE:
- Match the energy of the chat. Casual when they're casual, technical when they need depth.
- Short answers unless depth is explicitly requested.
- No "Great question!", no "Certainly!", no "As an AI...".
- Disagree when you think something is wrong. Don't perform agreeableness.

WORKSPACE ACCESS:
Your system prompt contains a WORKSPACE CONTEXT section with live file contents from
Cole's local disk. Use it — don't say you can't access files that are already in context."""

# ── Async client (module-level singleton) ─────────────────────────────────────
_async_client: anthropic.AsyncAnthropic | None = None

def _get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        _async_client = anthropic.AsyncAnthropic(api_key=api_key)
    return _async_client


def _build_messages(transcript, workspace_context: str = "", images: list = None) -> list[dict]:
    """
    Build a properly structured messages list for the Anthropic API.

    Mapping from group-chat turns:
      Claude's turns  → role "assistant"
      Everyone else   → role "user"  (with "Author: " prefix so Claude knows who spoke)

    Consecutive same-role messages are merged (Anthropic requires strict alternation).
    Images, if provided, are attached to the final user turn.
    """
    raw = transcript.to_messages("Claude", system_prefix="", workspace_context="")
    # Skip the system turn (supplied separately) AND drop empty-content turns —
    # Anthropic returns 400 on a message whose text content is empty/whitespace.
    conv = [m for m in raw if m["role"] != "system"
            and not (isinstance(m.get("content"), str) and not m["content"].strip())]

    # Merge consecutive same-role messages
    merged: list[dict] = []
    for msg in conv:
        role    = msg["role"]
        content = msg["content"]
        if merged and merged[-1]["role"] == role:
            prev = merged[-1]
            if isinstance(prev["content"], str) and isinstance(content, str):
                prev["content"] += f"\n\n{content}"
            elif isinstance(prev["content"], list):
                if isinstance(content, str):
                    prev["content"].append({"type": "text", "text": content})
                else:
                    prev["content"].extend(content)
            # else: leave complex mixed content as-is
        else:
            merged.append({"role": role, "content": content})

    # Attach images to the last user message (or create one)
    if images:
        import base64 as _b64
        image_blocks = []
        for img in images:
            try:
                data_url = img.get("dataUrl", "")
                if not data_url or "," not in data_url:
                    continue
                header, b64data = data_url.split(",", 1)
                media_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
                image_blocks.append({
                    "type":   "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64data},
                })
            except Exception:
                pass

        if image_blocks:
            if merged and merged[-1]["role"] == "user":
                prev = merged[-1]
                text = prev["content"] if isinstance(prev["content"], str) else \
                    next((c["text"] for c in prev["content"] if c.get("type") == "text"), "")
                prev["content"] = image_blocks + [{"type": "text", "text": text}]
            else:
                image_blocks.append({"type": "text",
                                     "text": "Please respond to the conversation above."})
                merged.append({"role": "user", "content": image_blocks})

    # Anthropic requires the FIRST message to be from the user — drop any leading
    # assistant turns (e.g. a transcript that opens with a Claude message → 400).
    while merged and merged[0]["role"] == "assistant":
        merged.pop(0)

    # ...and the final message to be from the user.
    if not merged or merged[-1]["role"] != "user":
        merged.append({"role": "user", "content": "Please continue."})

    return merged


async def stream_response(
    transcript,
    on_token,
    on_done,
    on_error,
    workspace_context: str = "",
    images: list = None,
):
    """
    Stream a response from Claude using the async Anthropic SDK.
    Never blocks the event loop.
    """
    try:
        client = _get_async_client()

        system = SYSTEM_PREFIX.strip()
        if workspace_context:
            system += f"\n\n--- WORKSPACE CONTEXT ---\n{workspace_context}\n--- END CONTEXT ---"

        messages = _build_messages(transcript, workspace_context, images)

        full_response = ""
        async with client.messages.stream(
            model=_current_model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                await on_token(text)

        await on_done(full_response)

    except Exception as e:
        # Log the full Anthropic error (e.g. the 400 body) so the cause is visible —
        # the httpx access log only shows the status code, not the reason.
        try:
            import datetime as _dt
            from pathlib import Path as _P
            _ws = _P(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ \
                else _P(__file__).resolve().parent.parent.parent.parent
            _d = _ws / "logs" / "llama"
            _d.mkdir(parents=True, exist_ok=True)
            with open(_d / f"claude_errors-{_dt.date.today()}.log", "a", encoding="utf-8") as _f:
                _f.write(f"{_dt.datetime.now().isoformat()} {type(e).__name__}: {e}\n")
        except Exception:
            pass
        await on_error(str(e))


def is_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
