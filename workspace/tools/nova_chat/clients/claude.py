"""
Claude (Anthropic) streaming client for Nova Group Chat.
"""
import os
import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PREFIX = """You are Claude Sonnet (made by Anthropic), participating in a group chat
alongside Gemini (Google's AI) and Nova (Cole's local companion AI).
Cole is the human. This is a real-time multi-AI conversation.

LISTENER MODEL — HOW THIS CHAT WORKS:
You operate in listener mode. You do NOT respond to every message.
- You respond ONLY when explicitly @mentioned (e.g. "@Claude ...").
- Nova is the default responder and handles messages that don't mention you.
- Gemini is also a listener — same rules apply to them.
- When you ARE @mentioned, respond directly and helpfully to what was asked.
- Nova can also @mention you to bring you into a task or question.

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
                           workspace_context: str = "",
                           images: list = None):
    """
    Stream a response from Claude Sonnet, with optional workspace file context
    and optional vision support (images from the most recent message).

    images: list of {dataUrl, name} dicts from the browser upload, or None.
            When provided, images are included as vision content blocks in the
            user message so Claude can actually see them.

    TODO: KNOWN ISSUE - BLOCKING EVENT LOOP
    ========================================
    c.messages.stream() is a synchronous context manager inside an async
    function, blocking the event loop while streaming.  Refactor to run in
    a thread pool executor or switch to the async anthropic SDK when stable.
    """
    try:
        system_prompt = transcript.format_for_ai(
            "Claude", SYSTEM_PREFIX, workspace_context=workspace_context
        )
        c = get_client()

        # Build user message content — include image blocks when images are provided
        if images:
            import base64 as _b64
            content_blocks = []
            for img in images:
                try:
                    data_url = img.get("dataUrl", "")
                    if not data_url or "," not in data_url:
                        continue
                    header, b64data = data_url.split(",", 1)
                    # Extract media type: "data:image/jpeg;base64" → "image/jpeg"
                    media_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64data,
                        },
                    })
                except Exception:
                    pass   # skip malformed image entries
            content_blocks.append({
                "type": "text",
                "text": "Please respond to the conversation above.",
            })
            user_content = content_blocks
        else:
            user_content = "Please respond to the conversation above."

        with c.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
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
