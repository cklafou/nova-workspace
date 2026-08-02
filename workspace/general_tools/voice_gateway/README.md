# voice_gateway — Cole's microphone to Nova

The pipe that lets you **talk** to Nova and **hear** her back, on the desktop first
(smartwatch → phone → tunnel → this same gateway comes later). It is a **comms tool, not a
faculty** — the pluck test holds: delete this folder and Nova is completely unchanged; she just
has no mic. It speaks nova_chat's **existing** WebSocket protocol from the outside, exactly like
the browser UI, so **no change to her body or her chat server is required to run it.**

```
   mic ─▶ VAD (Silero) ─▶ STT (Moonshine) ─▶ nova_chat WS  ──▶  Nova (her full mind + witness)
                                                   ▲                        │
   speakers ◀─ TTS (Chatterbox) ◀─ sentence-committer ◀── her token/reply stream
```

## What makes it fast enough for voice
- **Sentence-committer** (`committer.py`) chunks her reply into sentences so TTS starts speaking
  sentence 1 while sentence 2 is still being written — first audio in ~1–2s instead of after the
  whole reply. This is the one piece with real logic, so it has unit tests (`test_committer.py`,
  9/9 passing).
- **Voice register** (already in `nova.py`): a voice turn caps the witness at **2 rounds** instead
  of 20 — a person on a watch can't wait out a 20-round audit debate, and the **heavy-witness
  cloud lane** settles any dispute *after* her words are already spoken (logs-only), so capping
  loses nothing but waiting. `voice_fast` additionally skips the reasoning pass on casual replies.
  (Honoring the register needs the small `server_patch.md`; the gateway runs without it.)
- **Safe by default**: `speak_from="final"` speaks only her **witness-approved** `message_end`
  text — nothing unaudited is ever spoken. `speak_from="stream"` (faster, pre-audit) is opt-in
  for casual/`voice_fast` turns.

## The smoke ladder — verify each layer before wiring audio
Run these in order; each needs only the tier below it, and the gateway is useful at every rung.

| # | command | proves | needs |
|---|---------|--------|-------|
| 1 | `python general_tools/voice_gateway/test_committer.py` | the committer logic | nothing |
| 2 | `python general_tools/voice_gateway/gateway.py --smoke-link "hey nova, what's up"` | transport + committer against a **running Nova** | `pip install websockets` |
| 3 | `python general_tools/voice_gateway/gateway.py --smoke-tts "this is my voice test"` | committer → TTS | a TTS backend (or Null logs) |
| 4 | `python general_tools/voice_gateway/gateway.py --run` (with `stt_backend='stdin'`) | the **whole loop** — type to her, hear her reply | TTS; mic optional |

Rung 2 is the important one: it confirms Cole-speech-in and Nova-reply-out over the real socket,
with zero audio stack. Rung 4 with `stdin` STT is the full gateway minus the microphone.

## Install (tiered — see `requirements.txt`, `fetch_models.cmd`)
1. **Transport**: `pip install websockets` → rung 2 works.
2. **Voice out**: Chatterbox (`pip install torch chatterbox-tts`, expressive, recommended) **or**
   llama.cpp TTS (`tts_backend='llamacpp'` + a TTS gguf — uses the `llama-tts.exe` already here).
3. **Mic in**: `pip install sounddevice numpy onnxruntime useful-moonshine-onnx silero-vad`.
   Until then, `stt_backend='stdin'`.

## Config
`config.py` holds every knob; override via `_admin/voice_gateway.json` or `VOICE_GW_*` env vars.
Key ones: `register` (`voice`/`voice_fast`/`text`), `speak_from` (`final`/`stream`), `tts_backend`
(`auto`/`chatterbox`/`llamacpp`/`null`), `tts_reference_wav` (voice clone clip), `stt_backend`
(`moonshine`/`stdin`).

## What needs Cole (the parts the autonomous build deliberately stopped at)
- **A voice to pick** — the audition round: produce candidate Chatterbox reference clips and
  choose one with Nova. Casting decision, not code.
- **The audio stack** — installing torch/Chatterbox/Moonshine and a mic/speakers, then walking
  the smoke ladder on real hardware.
- **`server_patch.md`** — the tiny server edit that makes voice turns honor the register cap
  (best applied with the server running so one turn can be watched before/after).

## Status
Built and compile-clean: committer (+tests), config, nova_link, stt (Moonshine/Silero + stdin
fallback), tts (Chatterbox/llama.cpp/Null), gateway (all four smoke modes). Untested against live
audio — that's the hardware bringup above. The transport smoke (rung 2) can be run the moment
Nova is up and `websockets` is installed.
