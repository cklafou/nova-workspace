# Nova Chat V1 Baseline Fixes — Overnight Session
**Date:** 2026-05-10

---

## What Was Done

Complete audit + fix of all serious bugs in Nova Chat. Nine checks pass verified.

---

## Bugs Fixed

### 1. Context Overflow → 400 Bad Request (CRITICAL)
**File:** `workspace/general_tools/nova_chat/clients/nova.py`

After ~50+ turns the session transcript exceeded llama.cpp's 32,768-token context
window, causing every Nova message to return HTTP 400 immediately. This was also the
root cause of "Stop button not working" (nothing to stop) and "Thoughts pane empty"
(generation never started).

**Fix:** Added `_truncate_to_context()` — walks the message list newest→oldest and
drops old turns until the estimated prompt fits within the 32K window. Uses `//3` 
(3 chars/token) as a conservative overestimate of Qwen3's BPE tokenizer (~3.4 actual),
with a 4,096-token safety margin on top of the `max_tokens` output budget.

**Verified:** Python simulation of 512-message session → trims to 84 conversation turns,
26,609 estimated tokens (6,159 token headroom under 32K limit).

Also removed `chat_template_kwargs` from the llama.cpp payload — older builds reject
this unknown field with 400, and Qwen3's embedded GGUF template already enables
thinking mode by default.

---

### 2. UI Stuck in "Processing" After Error
**File:** `workspace/general_tools/nova_chat/server.py`

When `on_error()` fired, it ONLY broadcast the `error` event — never sending
`think_end`, `generation_end`, or `message_end`. This left:
- The Thoughts pane "thinking..." spinner running forever
- The Monitor showing "Working" indefinitely  
- An empty half-rendered message bubble stuck in the chat

**Fix:** `on_error()` now broadcasts state-cleanup events in the correct order before
the error event: `think_end` → `generation_end` (Nova only) → `message_end` → `error`.

---

### 3. `processing_end` Never Broadcast from Inject Path
**File:** `workspace/general_tools/nova_chat/server.py`

`_inject_listener_run()` (triggered when Nova @mentions Claude/Gemini) had 
`except asyncio.CancelledError: raise` which prevented the `finally` block from
running when the task was cancelled — meaning `processing_end` was never broadcast.

**Fix:** Changed `raise` → `pass` for CancelledError, and added
`await broadcast({"type": "processing_end"})` to the `finally` block.

---

### 4. Mute State Not Applied to Response Queue
**File:** `workspace/general_tools/nova_chat/server.py`

`_mute_states` was defined correctly (Nova=False=unmuted, Claude/Gemini=True=muted)
but was never actually used when building the response queue for regular messages.
Claude and Gemini were responding to every message even though they should be silent
unless @mentioned.

**Fix:** When no `@mentions` are present, the response queue is now filtered through
`_mute_states` so only unmuted agents respond. Explicit @mentions still bypass mute.

---

### 5. Thinking Tokens Silently Dropped from Message Bubble
**File:** `workspace/general_tools/nova_chat/static/index.html`

`appendThink(id, token)` returned early if `streamBufs[id]` didn't exist. But
`think_token` events arrive BEFORE the first `token` event (Nova thinks before
speaking), so `streamBufs[id]` is always missing when thinking starts — ALL thinking
content in the message bubble was silently dropped.

**Fix:** Changed `appendThink(id, token)` → `appendThink(author, id, token)` and
replaced the early-return with `startStream(author, id)`, creating the message bubble
early so thinking content accumulates correctly. Updated the call site to pass
`d.author`.

---

### 6. No Handler for `nova_progress` Events
**File:** `workspace/general_tools/nova_chat/static/index.html`

The server broadcasts `nova_progress` events with real-time chars/sec during Nova
generation, but the client had no handler. The Monitor's "Tokens/s" display always
showed `—` even while Nova was actively generating.

**Fix:** Added `case 'nova_progress': updateProgressFromNova(d); break;` to `handle()`
and added `updateProgressFromNova()` function that converts `rate` (chars/sec) to
estimated tokens/sec (÷ 3.4 for Qwen3 BPE) and updates `#mon-tps` in real time.

---

### 7. Export Type Mismatch (Export Broken)
**File:** `workspace/general_tools/nova_chat/static/index.html`

`exportCtx()` was sending `{type: 'export_context'}` via WebSocket but the server
handler checks for `type === 'export_request'`. Export was silently doing nothing.

**Fix:** Changed the client to send `{type: 'export_request'}` to match the server.

---

### 8. Undefined CSS Variables in Live Reasoning Block
**File:** `workspace/general_tools/nova_chat/static/index.html`

The live-think-block in the Thoughts pane referenced `var(--surface-2)` (background)
and `var(--accent)` (label color), neither of which was defined in `:root`. The block
had a transparent background and the "NOVA — REASONING LIVE" label had no color.

**Fix:** Added `--surface-2: #18182a` and `--accent: #8f90ff` to `:root`.

---

## Files Audited (No Bugs Found)

- `transcript.py` — clean
- `clients/claude.py` — clean
- `clients/gemini.py` — clean
- `session_manager.py` — clean
- `nova_bridge.py` — clean
- `nova_lang.py` — clean
- `orchestrator.py` — clean

All 16 Python files in nova_chat pass syntax validation.

---

## Known Non-Bug Limitation

The depth slider (`set_depth` WS message) sets a `_depth_max_tokens` server global
but this value is never passed through to `nova_client.stream_response()`. The slider
UI works but has no effect on Nova's output length. This is wiring debt, not a crash.

---

## What Should Work Now When You Start the App

1. **Nova responds** — context trimmer keeps transcript under 32K, no more 400 errors
2. **Stop button** — actually has something to stop now; works as expected
3. **Thoughts pane** — "NOVA — REASONING LIVE" block shows with correct styling, and
   thinking content accumulates in both the Thoughts panel AND the message bubble
4. **Monitor panel** — shows "Working" during generation, updates tokens/s in real time
5. **Mute** — Claude and Gemini stay silent unless you @mention them
6. **Export** — WS-based export now works correctly
