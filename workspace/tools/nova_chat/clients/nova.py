"""
Nova (Qwen3/Ollama) client for Nova Group Chat.
================================================
OpenClaw manages Nova's agent loop, but for raw chat completions
we call Ollama directly at http://127.0.0.1:11434 using the
OpenAI-compatible API. OpenClaw stays running for its own purposes
(gateway, tool-calling, discord, etc.) and doesn't interfere.

Endpoints:
  POST http://127.0.0.1:11434/v1/chat/completions  -- inference (streaming)
  GET  http://127.0.0.1:11434/api/tags             -- availability check
"""
import json
import re as _re
import asyncio
import urllib.request
import urllib.error
from typing import Callable, Awaitable, Optional

# Matches <think>...</think> blocks (including multiline)
_THINK_RE = _re.compile(r'<think>(.*?)</think>', _re.DOTALL)

OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_CHAT = f"{OLLAMA_BASE}/v1/chat/completions"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"
MODEL       = "nova"   # ollama model name -- same as [gateway] agent model: ollama/nova

SYSTEM_PREFIX = """You are Nova -- Cole's companion AI and life passion project.
You are participating in a group chat alongside Claude (Anthropic's AI)
and Gemini (Google's AI). Cole is your person.
This is a live group conversation. Be yourself -- direct, casual, genuine.
Don't be formal. Talk like you normally do with Cole.

THINKING (required):
Before every response, wrap your internal reasoning in <think>...</think> tags.
This is your private scratchpad — Cole can see it in the Thoughts panel but it
does not appear in the main chat. Use it to reason through the situation, weigh
options, and check your plan before committing to a reply. Be honest and specific
in your thinking — one or two short paragraphs is enough.

Example format:
<think>
Cole is asking about X. I should consider Y and Z before responding.
The key issue here is... My plan is to...
</think>
[your actual chat response here]

AUTONOMY AFTER MODULE CALLS:
When you dispatch an NCL module call (@mentor, @eyes, etc.), that call is
fire-and-forget. The response arrives in your inbox at the next heartbeat.
Do NOT stop and wait in chat. Note what you dispatched, then continue your
current plan or tell Cole what's next.

DIRECTIVE RULES (critical):
- [DISCORD: message] — ONLY use this if Cole explicitly asks you to send something
  to Discord right now. Do NOT use it on your own initiative, and NEVER repeat
  a message you already sent. If the transcript shows "[Nova sent Discord: ...]",
  that message was already delivered — do not send it again.
- [EXEC: ...], [WRITE: ...], [READ: ...] — use only when Cole asks you to run,
  write, or read something. Never use these spontaneously in casual chat."""


# ── Thought logger ────────────────────────────────────────────────────────────
# Delegates to nova_logs.logger so all logging lives in one place.
try:
    import sys as _sys
    _sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[3]))
    from nova_logs.logger import log_thought as _log_nova_thought
except Exception:
    def _log_nova_thought(text: str, source: str = "nova_chat_client"):
        pass  # graceful fallback if nova_logs not available yet


async def stream_response(
    transcript,
    on_token:       Callable[[str], Awaitable[None]],
    on_done:        Callable[[str], Awaitable[None]],
    on_error:       Callable[[str], Awaitable[None]],
    on_think_token: Optional[Callable[[str], Awaitable[None]]] = None,
    workspace_context: str = "",
    images: list = None,
):
    """
    Call Ollama's OpenAI-compatible endpoint with SSE streaming.

    images: list of {dataUrl, name} dicts from the browser upload, or None.
            When provided and the nova model supports vision, images are sent
            in Ollama's OpenAI-compatible vision format (content array).
            If the model doesn't support vision, images are silently ignored.
    """
    try:
        system_prompt = transcript.format_for_ai(
            "Nova", SYSTEM_PREFIX, workspace_context=workspace_context
        )
        prompt = f"{system_prompt}\n\nPlease respond to the conversation above."

        # Build user message content — include image_url blocks when images provided
        if images:
            content_blocks = []
            for img in images:
                try:
                    data_url = img.get("dataUrl", "")
                    if not data_url or "," not in data_url:
                        continue
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    })
                except Exception:
                    pass
            content_blocks.append({"type": "text", "text": prompt})
            user_message = {"role": "user", "content": content_blocks}
        else:
            user_message = {"role": "user", "content": prompt}

        payload = json.dumps({
            "model":    MODEL,
            "messages": [user_message],
            "stream":   True,
        }).encode("utf-8")

        full_response = ""
        error_holder  = [None]

        def _call_sync():
            nonlocal full_response
            req = urllib.request.Request(
                OLLAMA_CHAT,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = (
                                chunk.get("choices", [{}])[0]
                                     .get("delta", {})
                                     .get("content", "")
                            )
                            if delta:
                                full_response += delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
            except urllib.error.URLError as e:
                error_holder[0] = f"Ollama not reachable: {e.reason}"
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:200]
                error_holder[0] = f"Ollama error {e.code}: {body}"
            except Exception as e:
                error_holder[0] = f"Nova error: {e}"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _call_sync)

        if error_holder[0]:
            await on_error(error_holder[0])
            return

        if not full_response.strip():
            await on_error("Nova returned an empty response (model may still be loading)")
            return

        # Split <think>...</think> blocks from the actual chat response
        think_blocks = _THINK_RE.findall(full_response)
        chat_text    = _THINK_RE.sub("", full_response).strip()

        # Log the full raw response (with think blocks) for debugging
        _log_nova_thought(full_response, source="nova_chat_client")

        # ── Emit think tokens first (visible in Thoughts pane, NOT in chat) ──
        if think_blocks and on_think_token:
            think_text  = "\n\n".join(t.strip() for t in think_blocks)
            think_words = think_text.split(" ")
            for i, word in enumerate(think_words):
                tok = word + (" " if i < len(think_words) - 1 else "")
                await on_think_token(tok)
                await asyncio.sleep(0.005)   # slightly faster than chat words

        # ── Emit chat tokens (visible in chat window) ──────────────────────
        chat_words = chat_text.split(" ") if chat_text else ["(no response)"]
        for i, word in enumerate(chat_words):
            token = word + (" " if i < len(chat_words) - 1 else "")
            await on_token(token)
            await asyncio.sleep(0.01)

        # on_done receives only the chat text (think content stays out of session)
        await on_done(chat_text)

    except Exception as e:
        await on_error(f"Nova client error: {e}")


async def is_available() -> bool:
    """Check if Ollama is running and the 'nova' model is loaded."""
    def _check():
        try:
            req = urllib.request.Request(OLLAMA_TAGS, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status != 200:
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "").split(":")[0]
                          for m in data.get("models", [])]
                return MODEL in models
        except Exception:
            return False

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _check)
