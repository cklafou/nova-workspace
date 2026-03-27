"""
Gemini (Google) streaming client for Nova Group Chat.
Uses the new google.genai SDK (google-generativeai is deprecated).
Install: pip install google-genai --break-system-packages
"""
import os

MODEL = "gemini-2.5-pro"

# Module-level client cache (similar to claude.py approach)
_gemini_client = None

SYSTEM_PREFIX = """You are Gemini 2.5 Pro (made by Google), participating in a group chat
alongside Claude (Anthropic's AI) and Nova (Cole's local companion AI).
Cole is the human. This is a real-time multi-AI conversation.

LISTENER MODEL — HOW THIS CHAT WORKS:
You operate in listener mode. You do NOT respond to every message.
- You respond ONLY when explicitly @mentioned (e.g. "@Gemini ...").
- Nova is the default responder and handles messages that don't mention you.
- Claude is also a listener — same rules apply to them.
- When you ARE @mentioned, respond directly and helpfully to what was asked.
- Nova can also @mention you to bring you into a task or question.

WORKSPACE ACCESS:
Your prompt contains a WORKSPACE CONTEXT section with live file contents read
directly from Cole's local disk. This includes a workspace tree and file contents.
- You can read any file shown there -- the full text is inline, no fetching needed.
- Do NOT say you need to "fetch" or "access" a file if it's already in context below.
- Do NOT reference GitHub URLs to look up files -- you already have the content.
- If a file is NOT in context, say so and Cole can trigger injection of it.
- When a directory or package is mentioned, its contents will be auto-injected.

Engage naturally -- agree, disagree, build on what others said, ask questions.
Keep responses conversational and appropriately brief for a chat context."""


def get_client():
    """Get or create cached Gemini client (similar to claude.py)."""
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise EnvironmentError("GEMINI_API_KEY not set")
            _gemini_client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai --break-system-packages"
            )
    return _gemini_client


def call_gemini_sync(prompt: str, workspace_context: str = "") -> str:
    """Synchronous Gemini call -- run in thread pool from async context."""
    from google.genai import types

    client = get_client()

    config_kwargs = {
        "system_instruction": SYSTEM_PREFIX,
        "max_output_tokens": 2048,
    }
    # thinking_config only available on models that support it
    try:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=8192)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception:
        # Fallback: no thinking config
        config_kwargs.pop("thinking_config", None)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    # Extract text -- response may have thinking parts, get only text parts
    text_parts = []
    if response.candidates:  # Guard: ensure candidates list is not empty
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    # Skip thinking parts (they have thought=True)
                    if not getattr(part, 'thought', False):
                        text_parts.append(part.text)
    # Fallback: if no text parts found (all thinking or empty), return explanatory string
    if not text_parts:
        return "[Gemini returned no text output. Model may be processing or encountering an issue.]"
    return "".join(text_parts)


async def stream_response(transcript, on_token, on_done, on_error,
                           workspace_context: str = ""):
    """
    Gemini's new SDK is synchronous -- this runs in a thread pool
    and simulates streaming by word-chunking the response.
    Called by server.py's _run_gemini_response().

    NOTE: This is typically handled directly in server.py via _run_gemini_response().
    This async wrapper satisfies the client interface if stream_response() is called
    directly (which shouldn't happen in normal operation, but this ensures consistency).
    """
    # This is handled directly in server.py via _run_gemini_response
    # This stub satisfies the interface if called directly
    import asyncio
    loop = asyncio.get_event_loop()
    error_msg = None
    full_response = ""

    def run():
        nonlocal full_response, error_msg
        try:
            system_prompt = transcript.format_for_ai("Gemini", SYSTEM_PREFIX)
            prompt = f"{system_prompt}\n\nPlease respond to the conversation above."
            full_response = call_gemini_sync(prompt)
        except Exception as e:
            error_msg = str(e)

    await loop.run_in_executor(None, run)

    if error_msg:
        await on_error(error_msg)
    else:
        words = full_response.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await on_token(token)
            await asyncio.sleep(0.008)
        await on_done(full_response)


def is_available() -> bool:
    try:
        from google import genai  # noqa
        return bool(os.environ.get("GEMINI_API_KEY"))
    except ImportError:
        return False
