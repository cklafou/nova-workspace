<!-- @nova: Describe the voice gateway scaffold, verified readiness and the remaining delivery and audio integration work. -->
# voice_gateway — Cole's microphone to Nova
_Last updated: 2026-10-05 21:33:07_

The pipe that lets you **talk** to Nova and **hear** her back, on the desktop first
(smartwatch → phone → tunnel → this same gateway comes later). It is a **comms tool, not a
faculty** — the pluck test holds: delete this folder and Nova is completely unchanged; she just
has no mic. It speaks nova_chat's **existing** WebSocket protocol from the outside, exactly like
the browser UI, so basic text transport can reuse that connection. End-to-end voice still needs the integration below.

```
   mic ─▶ VAD (Silero) ─▶ STT (Moonshine) ─▶ nova_chat WS  ──▶  Nova (her full mind + witness)
                                                   ▲                        │
   speakers ◀─ TTS (Chatterbox) ◀─ sentence-committer ◀── her token/reply stream
```

## Current integration limits (2026-10-04)

The sentence committer is implemented, but live speech latency has not been measured. The
current human-facing model path holds tokens during audit, so final-message playback is the
first integration target. Do not promise early speech while that hold is active.

- `speak_from="final"` uses delivered `message_end` text. Delivery can follow an INCOMPLETE or
  ERROR audit; it does **not** mean witness approval. The event still needs an explicit audit
  disposition for downstream voice/body presentation.
- `speak_from="stream"` currently flushes only received tokens. When the server holds them,
  this can yield silence despite a nonempty final reply. The claim tagger annotates sentences;
  it does not hold them back from `_emit`/TTS.
- `NovaLink.replies()` currently discards message IDs, and the full gateway ignores start
  events. ID preservation, per-message reset, interruption and queued-audio flush are required
  before overlapping turns or body events are reliable.
- The voice `register` is not carried through the current server queue/runtime model-client
  path. `server_patch.md` is an older sketch, not an applied patch against today's route.
  Capping witness correction rounds would not cap all model requests or wall-clock time.
- First-stage scope agreed in Collaboration: delivered final text, IDs, start/interrupt/flush,
  audit status and body events. Speculative pre-audit speech remains a later design decision.

Readiness was checked with Python 3.12.6 on October 4 at 18:37, with Nova off: `websockets`,
NumPy, Torch and Transformers were present; sounddevice, ONNX Runtime, torchaudio,
Chatterbox, Silero VAD and Moonshine were absent in that interpreter. No microphone, live
TTS, VTube Studio API or lip-sync was validated. `VOICE_CHECK.cmd` regenerates the local report.

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
1. **Transport**: `websockets` is required for rung 2; a successful exchange must still be tested.
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
- **Routing and delivery integration** — follow the current queue and runtime client; use
  `server_patch.md` only as background. Verify final-text fallback and interruption before audio.

## Status
Built and compile-clean: committer (+tests), config, nova_link, stt (Moonshine/Silero + stdin
fallback), tts (Chatterbox/llama.cpp/Null), gateway (all four smoke modes). Untested against live
audio and still missing the delivery fixes above. The transport smoke (rung 2) can be run the moment
Nova is up and `websockets` is installed.
