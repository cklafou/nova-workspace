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
import asyncio
import urllib.request
import urllib.error
from typing import Callable, Awaitable

OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_CHAT = f"{OLLAMA_BASE}/v1/chat/completions"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"
MODEL       = "nova"   # ollama model name -- same as [gateway] agent model: ollama/nova

SYSTEM_PREFIX = """You are Nova -- Cole's companion AI and life passion project.
You are participating in a group chat alongside Claude (Anthropic's AI)
and Gemini (Google's AI). Cole is your person.
This is a live group conversation. Be yourself -- direct, casual, genuine.
Don't be formal. Talk like you normally do with Cole."""


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
    on_token:  Callable[[str], Awaitable[None]],
    on_done:   Callable[[str], Awaitable[None]],
    on_error:  Callable[[str], Awaitable[None]],
    workspace_context: str = "",
):
    """Call Ollama's OpenAI-compatible endpoint with SSE streaming."""
    try:
        system_prompt = transcript.format_for_ai(
            "Nova", SYSTEM_PREFIX, workspace_context=workspace_context
        )
        prompt = f"{system_prompt}\n\nPlease respond to the conversation above."

        payload = json.dumps({
            "model":    MODEL,
            "messages": [{"role": "user", "content": prompt}],
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

        # Write to thought log so Cole can see Nova's reasoning in real time
        _log_nova_thought(full_response, source="nova_chat_client")

        # Word-chunk the completed response to simulate streaming
        words = full_response.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await on_token(token)
            await asyncio.sleep(0.01)

        await on_done(full_response)

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
