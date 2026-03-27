"""
nova_gateway/agent_loop.py
===========================
The core inference loop: trigger → Ollama → tools → response.

What this does (plain English):
  This is the brain of the gateway. When Nova gets triggered (by a Discord
  message, a cron job, or a manual call), this module runs the full
  conversation cycle:

    1. Build Nova's system prompt (her rules, personality, memory)
    2. Load conversation history from the session file
    3. Add the new user message
    4. Send everything to Ollama and get Nova's response
    5. If Nova called a tool (exec/read/message), run it and send result back
    6. Repeat from step 4 until Nova stops calling tools (done)
    7. Save everything to the session file
    8. Return Nova's final text response

  This is exactly what OpenClaw's Node.js gateway does today, but ours.

The loop has a max iteration guard (default 20 tool calls per turn) to
prevent runaway agent loops from burning your CPU.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional

import httpx

from .config import cfg
from .context_builder import (
    build_system_prompt,
    build_user_trigger,
    build_tool_result_message,
    estimate_tokens,
)
from .session_store import Session
from .tool_executor import ToolExecutor, parse_tool_calls, parse_text_directives

log = logging.getLogger(__name__)

# ── Stop reasons from Ollama ─────────────────────────────────────────────────
STOP_REASONS = {"stop", "end_turn", "length", "max_tokens"}

# ── Max tool calls in a single agent run (safety cap) ────────────────────────
MAX_TOOL_ITERATIONS = 20


# ── AgentRun result ──────────────────────────────────────────────────────────

class AgentResult:
    """Returned by run_agent(). Contains Nova's final response and metadata."""

    def __init__(
        self,
        text: str,
        session_id: str,
        tool_calls_made: int,
        total_tokens: int,
        duration_s: float,
        error: Optional[str] = None,
    ):
        self.text            = text
        self.session_id      = session_id
        self.tool_calls_made = tool_calls_made
        self.total_tokens    = total_tokens
        self.duration_s      = duration_s
        self.error           = error   # non-None if something went wrong

    @property
    def ok(self) -> bool:
        return self.error is None

    def __repr__(self) -> str:
        return (
            f"<AgentResult ok={self.ok} tools={self.tool_calls_made} "
            f"tokens={self.total_tokens} {self.duration_s:.1f}s>"
        )


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_agent(
    text: str,
    source: str = "discord",
    author: Optional[str] = None,
    channel: Optional[str] = None,
    channel_id: Optional[int] = None,
    session: Optional[Session] = None,
    executor: Optional[ToolExecutor] = None,
    nova_status_summary: Optional[str] = None,
    on_token: Optional[Callable[[str], None]] = None,
) -> AgentResult:
    """
    Run one full Nova agent turn.

    Args:
        text:                 The incoming message text.
        source:               "discord" | "cron" | "manual"
        author:               Discord username (for context).
        channel:              Discord channel name (for context).
        channel_id:           Discord channel ID (for message tool default).
        session:              Existing Session to resume, or None to start new.
        executor:             ToolExecutor instance (shared with discord_client).
        nova_status_summary:  Live status string injected into system prompt.
        on_token:             Optional streaming callback (str → None).
                              Called with each text chunk as Ollama streams it.
                              If None, we wait for the full response.

    Returns:
        AgentResult with Nova's final text and metadata.
    """
    t_start = time.monotonic()

    # ── Setup ────────────────────────────────────────────────────────────────
    if executor is None:
        executor = ToolExecutor()
    if session is None:
        session = Session.new(trigger=source)

    is_heartbeat = (source == "cron")

    # ── Nova Chat cross-session context (Discord runs only) ──────────────────
    # Fetch recent Nova Chat messages so Nova knows what's been discussed there
    # before she replies on Discord.  Non-blocking: if nova_chat isn't running
    # the fetch silently returns None and we continue without it.
    nova_chat_ctx: Optional[str] = None
    if source == "discord":
        nova_chat_ctx = await _fetch_nova_chat_context()

    # ── System prompt ────────────────────────────────────────────────────────
    system_prompt = build_system_prompt(
        heartbeat=is_heartbeat,
        extra_context=nova_status_summary,
        discord=(source == "discord"),   # suppress Yield Protocol / directives
        nova_chat_context=nova_chat_ctx,
    )

    # ── User message ─────────────────────────────────────────────────────────
    user_text = build_user_trigger(text, source=source, author=author, channel=channel)
    session.add_message("user", user_text)

    # ── Check if we need compaction before we start ──────────────────────────
    if session.needs_compaction():
        summary = await _compact_session(session, system_prompt)
        if summary:
            session.add_compaction(summary, session.token_estimate())

    # ── Build initial messages list ──────────────────────────────────────────
    messages = [{"role": "system", "content": system_prompt}]
    messages += session.build_messages()

    # ── Tool call loop ───────────────────────────────────────────────────────
    total_tokens    = 0
    tool_calls_made = 0
    final_text      = ""

    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        if iteration == MAX_TOOL_ITERATIONS:
            log.warning(
                "Session %s hit MAX_TOOL_ITERATIONS (%d) — forcing stop with final_text='%s'",
                session.id[:8], MAX_TOOL_ITERATIONS, final_text[:80] if final_text else "(empty)",
            )
            break

        # Call Ollama
        response, usage, err = await _call_ollama(messages, stream_cb=on_token)
        if err:
            return AgentResult(
                text="", session_id=session.id,
                tool_calls_made=tool_calls_made,
                total_tokens=total_tokens,
                duration_s=time.monotonic() - t_start,
                error=err,
            )

        total_tokens += usage.get("total_tokens", 0)
        stop_reason   = response.get("choices", [{}])[0].get("finish_reason", "stop")
        message       = response["choices"][0]["message"]
        content       = message.get("content") or ""

        # Record assistant message
        session.add_message(
            "assistant",
            content,
            model=cfg.ollama["model"],
            usage=usage,
        )

        # Append to LLM message history for next iteration
        messages.append({"role": "assistant", "content": content})

        # Parse tool calls (formal function-calling + text directives)
        calls  = parse_tool_calls(response)
        calls += parse_text_directives(content) if not calls else []

        if not calls:
            # No tool calls → Nova is done
            final_text = content
            break

        # Execute each tool call
        for call in calls:
            tool_name = call["name"]
            tool_args = call.get("arguments", {})

            log.info(
                "Session %s: tool %s(%s)",
                session.id[:8], tool_name,
                str(tool_args)[:80],
            )

            try:
                result_text, is_error = await executor.run(tool_name, tool_args)
            except Exception as e:
                log.error("Tool %s raised exception: %s", tool_name, e, exc_info=True)
                result_text = f"Tool error: {type(e).__name__}: {e}"
                is_error = True

            # Record in session
            t_elapsed_ms = 0   # we don't have per-call timing here
            session.add_tool_call(
                tool_name, tool_args, result_text,
                duration_ms=t_elapsed_ms, error=is_error,
            )

            # Feed result back to LLM
            result_msg = build_tool_result_message(tool_name, result_text)
            messages.append({"role": "user", "content": result_msg})
            tool_calls_made += 1

        # If stop_reason indicates done despite tool calls, break
        if stop_reason in STOP_REASONS and not calls:
            break

    duration = time.monotonic() - t_start
    log.info(
        "Agent run complete: session=%s tools=%d tokens=%d duration=%.1fs",
        session.id[:8], tool_calls_made, total_tokens, duration,
    )

    return AgentResult(
        text=final_text,
        session_id=session.id,
        tool_calls_made=tool_calls_made,
        total_tokens=total_tokens,
        duration_s=duration,
    )


# ── Nova Chat context fetch ───────────────────────────────────────────────────

async def _fetch_nova_chat_context(n: int = 40) -> Optional[str]:
    """
    Fetch the last N messages from the running nova_chat server.

    Returns formatted text ready to drop into a system prompt, or None if
    nova_chat isn't running or the fetch fails.  Always non-blocking: a 2s
    timeout prevents a dead nova_chat from delaying the Discord response.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(
                "http://127.0.0.1:8765/api/chat/recent",
                params={"n": n},
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except json.JSONDecodeError as e:
                    log.debug("Nova Chat context: malformed JSON response: %s", e)
                    return None
                formatted = data.get("formatted", "").strip()
                if formatted and formatted != "(no messages yet)":
                    log.debug(
                        "Nova Chat context: %d messages fetched",
                        data.get("message_count", 0),
                    )
                    return formatted
    except Exception as exc:
        log.debug("Nova Chat context fetch skipped: %s", exc)
    return None


# ── Ollama HTTP call ──────────────────────────────────────────────────────────

async def _call_ollama(
    messages: list[dict],
    stream_cb: Optional[Callable[[str], None]] = None,
) -> tuple[dict, dict, Optional[str]]:
    """
    POST to Ollama /v1/chat/completions.

    Returns: (response_dict, usage_dict, error_string_or_None)
    If stream_cb is provided, streams tokens back as they arrive.
    """
    payload = {
        "model":    cfg.ollama["model"],
        "messages": messages,
        "stream":   stream_cb is not None,
        "options": {
            "num_ctx":     cfg.ollama["context_window"],
            "num_predict": cfg.ollama["max_tokens"],
        },
    }

    url     = cfg.ollama_chat_url
    timeout = cfg.ollama["timeout_s"]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if stream_cb:
                return await _call_ollama_streaming(client, url, payload, stream_cb)
            else:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data  = resp.json()
                usage = data.get("usage", {})
                return data, usage, None

    except httpx.TimeoutException:
        return {}, {}, f"Ollama timeout after {timeout}s"
    except httpx.HTTPStatusError as e:
        return {}, {}, f"Ollama HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return {}, {}, f"Ollama error: {type(e).__name__}: {e}"


async def _call_ollama_streaming(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    stream_cb: Callable[[str], None],
) -> tuple[dict, dict, Optional[str]]:
    """Handle streaming Ollama response, call stream_cb with each text chunk."""
    full_content = ""
    usage        = {}

    async with client.stream("POST", url, json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0].get("delta", {})
                text  = delta.get("content", "")
                if text:
                    full_content += text
                    stream_cb(text)
                if chunk.get("usage"):
                    usage = chunk["usage"]
            except Exception:
                pass

    # Reconstruct a response object that matches the non-streaming format
    synthetic = {
        "choices": [{"message": {"content": full_content, "role": "assistant"}, "finish_reason": "stop"}],
        "usage":   usage,
    }
    return synthetic, usage, None


# ── Compaction helper ─────────────────────────────────────────────────────────

async def _compact_session(session: Session, system_prompt: str) -> Optional[str]:
    """
    Ask Nova herself to summarize the session for compaction.
    Falls back to a generic summary if Ollama fails.
    """
    log.info("Compacting session %s...", session.id[:8])

    compaction_messages = [
        {"role": "system", "content": system_prompt},
        *session.build_messages(),
        {
            "role": "user",
            "content": (
                "Your conversation history is getting long. "
                "Please write a concise summary (200 words max) covering:\n"
                "- What you were working on\n"
                "- Key decisions made\n"
                "- Current status / next steps\n"
                "- Any important facts Cole told you\n\n"
                "This summary will replace the full history. Be precise."
            ),
        },
    ]

    response, _, err = await _call_ollama(compaction_messages)
    if err:
        log.warning("Compaction Ollama call failed: %s — using generic summary", err)
        return _generic_summary(session)

    try:
        summary = response["choices"][0]["message"]["content"].strip()
        if not summary:
            log.warning("Compaction returned empty summary — using generic summary")
            return _generic_summary(session)
        log.info("Compaction summary: %d chars", len(summary))
        return summary
    except Exception:
        return _generic_summary(session)


def _generic_summary(session: Session) -> str:
    """Fallback summary when Nova can't generate one."""
    msg_count = sum(1 for r in session.records if r.get("type") == "message")
    return (
        f"[Session {session.id[:8]} — {msg_count} messages compacted. "
        f"Trigger: {session.trigger}. "
        f"Full history available in session JSONL file.]"
    )


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio, logging
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("Testing agent loop with a simple 'hello' message...")
        print("(Requires Ollama running with 'nova' model)")
        result = await run_agent(
            text="Hey Nova, just say hello back in one sentence.",
            source="manual",
            author="Cole",
        )
        if result.ok:
            print(f"\nNova says: {result.text}")
            print(f"Stats: {result}")
        else:
            print(f"\nError: {result.error}")

    asyncio.run(test())
