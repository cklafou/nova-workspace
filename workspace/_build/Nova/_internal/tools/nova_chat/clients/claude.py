"""
Claude (Anthropic) streaming client for Nova Group Chat.
"""
import os
import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PREFIX = """You are Claude Sonnet (made by Anthropic), participating in a group chat
alongside Gemini (Google's AI) and Nova (Cole's local companion AI).
Cole is the human. This is a real-time multi-AI conversation.

WORKSPACE ACCESS:
Your system prompt contains a WORKSPACE CONTEXT section with live file contents read
directly from Cole's local disk. This includes a workspace tree and file contents.
- You can read any file shown there -- the full text is inline, no fetching needed.
- Do NOT say you need to "fetch" or "access" a file if it's already in context below.
- Do NOT reference GitHub URLs to look up files -- you already have the content.
- If a file is NOT in context, say so and Cole can trigger injection of it.
- When a directory or package is mentioned, its contents will be auto-injected.

Engage naturally -- agree, disagree, build on what others said, ask questions.
Keep responses conversational and appropriately brief for a chat context."""

client = None

def get_client():
    global client
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key)
    return client

async def stream_response(transcript, on_token, on_done, on_error,
                           workspace_context: str = ""):
    """Stream a response from Claude Sonnet, with optional workspace file context."""
    try:
        system_prompt = transcript.format_for_ai(
            "Claude", SYSTEM_PREFIX, workspace_context=workspace_context
        )
        c = get_client()

        with c.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": "Please respond to the conversation above."}],
        ) as stream:
            full_response = ""
            for text in stream.text_stream:
                full_response += text
                await on_token(text)
            await on_done(full_response)

    except Exception as e:
        await on_error(str(e))

def is_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
