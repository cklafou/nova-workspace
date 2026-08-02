# Optional server patch — thread the voice `register` to `stream_response`

**The gateway works without this.** At "text" register (the server's current default) a voice
turn runs with the full 20 witness rounds — correct, just slower under a dispute. This patch
lets the server honor the `register` field the gateway already sends, so voice turns cap witness
rounds at 2 (and `voice_fast` skips the reasoning pass on casual replies). `nova.py` is already
built for it — `stream_response(..., register="voice")` exists and branches. The only missing
link is the chat server passing the inbound field through.

Apply this with the server runnable so you can watch one voice turn before and after. It is a
few small, additive edits — nothing existing changes behavior, because every default stays
`"text"`.

## 1. WS `message` handler reads the field
In `general_tools/nova_chat/server.py`, the `@app.websocket("/ws")` handler, the
`if data.get("type") == "message":` block. Where it reads `content`/`images`/`speaker`, also:

```python
register = (data.get("register") or "text")
```

Then carry `register` into whatever run this path kicks off (the response-queue call). The run
machinery (`_run_response_queue` → `_generate` → the client call) needs to forward it as a
keyword argument, defaulting to `"text"` at every hop so no other caller is affected.

## 2. The client call passes it through
Wherever the server calls `client_mod.stream_response(...)` / `nova_client.stream_response(...)`
for a Cole turn, add:

```python
await client_mod.stream_response(session_mgr.active, on_token, on_done, on_error,
                                 register=register)
```

That is the whole change: read the field, forward it, pass it. `stream_response` already caps
rounds and (for `voice_fast`) skips thinking. Verify with one turn — the pipeline tab shows the
witness round count drop, and a disputed voice turn escalates to the heavy lane in ≤2 rounds
instead of grinding to 20.

## Why it's staged separately
Threading a kwarg through the live run/queue machinery is a change best made with the server
running so a single voice turn can be watched end to end. It is deliberately kept out of the
autonomous build, which only touched files that could be verified by compile + the golden
replay. Nothing here is required for the gateway to function.
