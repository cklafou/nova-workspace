# @nova: Connect microphone or typed input to Nova Chat and delivered replies to speech and avatar events.
#!/usr/bin/env python3
# Last updated: 2026-10-06 03:14:02
#   tool, not a faculty. Remove it and Nova is unchanged — she still thinks, still audits, still
#   writes; she just has no microphone. Her body is untouched: the gateway only speaks nova_chat's
#   existing WebSocket protocol from the OUTSIDE, exactly as the browser UI does.
"""
voice_gateway/gateway.py — mic → Nova → speakers, with a smoke-test ladder so every layer can
be verified independently before the whole thing is wired to audio hardware.

FIRST STAGE (agreed in the Collaboration room, 2026-10-05): speak only text Nova Chat DELIVERED
in reply to this gateway's own request (matched by request_id), with its audit status attached;
never diagnostics. New input retains committed queued speech; explicit Stop flushes it.
Only delivered audited segments/finals may speak; delivery does not imply audit approval.

THE SMOKE LADDER (run these in order as pieces come online):
  1. offline     python general_tools/voice_gateway/test_voice_flow.py    (no deps, no Nova)
                 python general_tools/voice_gateway/test_committer.py
  2. link        python general_tools/voice_gateway/gateway.py --smoke-link "hey nova, what's up"
                 → sends one utterance to a RUNNING Nova and prints the body events: the request's
                   acknowledgement, start, end classification and the units that would be spoken.
  3. tts         python general_tools/voice_gateway/gateway.py --smoke-tts "This is my voice test."
                 → runs text through the sanitizer + committer into the configured TTS backend.
  4. run         python general_tools/voice_gateway/gateway.py --run
                 → full loop. With stt_backend='stdin' you TYPE to her and hear her reply.

Config: general_tools/voice_gateway/config.py (+ _admin/voice_gateway.json). See README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from body import StdoutBody, make_body                    # noqa: E402
from committer import commit_block                         # noqa: E402
from config import GatewayConfig                           # noqa: E402
from speech import SpeechPlayer, speech_text               # noqa: E402
from turns import VoiceSession                             # noqa: E402


# ── rung 2: one request against a running Nova, no audio ──────────────────────────────────────
async def smoke_link(cfg: GatewayConfig, text: str, timeout_s: float = 600.0, *, audio=False):
    """A bounded real transport test; audio=True requires a real backend and uses the live sweep."""
    from nova_link import NovaLink, new_request_id
    from tts import NullTTS, make_tts
    body = StdoutBody()
    if audio and cfg.tts_backend == "auto" and sys.platform == "win32":
        cfg.tts_backend = "windows"
    tts = make_tts(cfg) if audio else NullTTS(cfg)
    if audio and tts.name == "null":
        tts.close()
        raise RuntimeError("Audio smoke test requires a real speech backend; NullTTS is not voice proof")
    print(f"[voice_gateway] transport test audio={audio}, TTS={tts.name}, register={cfg.register}: {text!r}")
    player = SpeechPlayer(tts, body, tail_s=0).start()
    sweeper = None
    try:
        async with NovaLink(cfg.nova_ws_url, cfg.speaker, cfg.register) as link:
            session = VoiceSession(cfg, player, body)
            request_id = new_request_id()
            session.sent(request_id, text)
            await link.say(text, request_id=request_id)

            async def sweep():
                while True:
                    await asyncio.sleep(5)
                    session.sweep()
            sweeper = asyncio.create_task(sweep())
            async def until_done():
                async for ev in link.events():
                    session.handle(ev)
                    if request_id not in session.pending:
                        return
                if request_id in session.pending:
                    raise RuntimeError("Voice link closed before the test reply was delivered")
            await asyncio.wait_for(until_done(), timeout=timeout_s)
            await player.drain()
    finally:
        if sweeper:
            sweeper.cancel()
            await asyncio.gather(sweeper, return_exceptions=True)
        await player.close()
        tts.close()
        body.close()
    print("[voice_gateway] transport test finished; consult speech outcomes for actual playback.")


# ── rung 3: sanitizer + committer + TTS backend, no transport ─────────────────────────────────
def smoke_tts(cfg: GatewayConfig, text: str):
    from tts import make_tts
    tts = make_tts(cfg)
    print(f"[voice_gateway] TTS backend: {tts.name}")
    for u in commit_block(speech_text(text), min_chars=cfg.min_chars, max_buffer=cfg.max_buffer):
        tts.speak(u.text)
    tts.close()


# ── rung 4: full run — STT → Nova → session → speech ─────────────────────────────────────────
async def run(cfg: GatewayConfig):
    from nova_link import NovaLink, new_request_id
    from stt import make_stt
    from tts import make_tts

    stt, tts, body = make_stt(cfg), make_tts(cfg), make_body(cfg)
    print(f"[voice_gateway] STT={stt.name}  TTS={tts.name}  register={cfg.register}  "
          f"scope={cfg.speak_scope}  duplex={cfg.duplex}  body={getattr(body, 'name', 'none')}")
    async with NovaLink(cfg.nova_ws_url, cfg.speaker, cfg.register) as link:
        player = SpeechPlayer(tts, body, tail_s=max(0, cfg.half_duplex_tail_ms) / 1000).start()
        session = VoiceSession(cfg, player, body)
        capture_active = False
        if cfg.duplex == "full" and cfg.barge_in:
            stt.on_speech_start = session.barge_in
        stt.gate = lambda: cfg.duplex == "full" or capture_active or not player.busy()

        def recognition_state(state):
            nonlocal capture_active
            if state in {"hearing", "finishing_turn", "transcribing"} and (cfg.duplex == "full" or capture_active or not player.active()):
                capture_active = True
                player.pause()  # Held replies cannot close a capture already in progress.
                body.emit("state", state=state)
            elif state == "listening":
                capture_active = False
                player.resume()  # Also releases after silence reset or recognition failure.
                session._settle()
        stt.on_state = recognition_state

        async def _listen():
            async for ev in link.events():
                if cfg.log_units and ev.kind == "end":
                    print(f"[voice_gateway] end {ev.message_id} delivery={ev.delivery} "
                          f"audit={ev.audit.get('status')}")
                session.handle(ev)

        async def _mic():
            async for utt in stt.utterances():
                print(f"[voice_gateway] {cfg.speaker}: {utt}")
                request_id = new_request_id()
                session.sent(request_id, utt)                # register before sending: no ack race
                player.resume()
                await link.say(utt, request_id=request_id)

        async def _sweep():
            while True:
                await asyncio.sleep(5)
                session.sweep()

        # Supervise both halves (Codex review #72): a dropped socket must not leave the mic
        # running, and a mic that ends must not leave a socket dangling.
        parts = {"mic": asyncio.ensure_future(_mic()), "link": asyncio.ensure_future(_listen())}
        sweeper = asyncio.ensure_future(_sweep())
        try:
            done, _ = await asyncio.wait(parts.values(), return_when=asyncio.FIRST_COMPLETED)
            for name, task in parts.items():
                if task in done:
                    error = None if task.cancelled() else task.exception()
                    message = f"{name} ended" + (f" with {type(error).__name__}: {error}" if error else "")
                    print(f"[voice_gateway] {message}; shutting the voice loop down.")
                    body.emit("diagnostic", level="error" if error else "info", message=message)
        finally:
            for task in (*parts.values(), sweeper):
                task.cancel()
            await asyncio.gather(*parts.values(), sweeper, return_exceptions=True)
            await player.close()
            stt.close()
            tts.close()
            body.close()


def main():
    ap = argparse.ArgumentParser(description="Nova voice gateway")
    ap.add_argument("--smoke-link", metavar="TEXT", help="send TEXT to a running Nova, print events + units")
    ap.add_argument("--smoke-audio", metavar="TEXT", help="send TEXT to Nova and play the delivered reply through real TTS")
    ap.add_argument("--smoke-tts", metavar="TEXT", help="run TEXT through sanitizer + committer + TTS")
    ap.add_argument("--run", action="store_true", help="full loop: STT → Nova → session → TTS")
    args = ap.parse_args()
    cfg = GatewayConfig.load()

    if args.smoke_link is not None:
        asyncio.run(smoke_link(cfg, args.smoke_link))
    elif args.smoke_audio is not None:
        asyncio.run(smoke_link(cfg, args.smoke_audio, audio=True))
    elif args.smoke_tts is not None:
        smoke_tts(cfg, args.smoke_tts)
    elif args.run:
        asyncio.run(run(cfg))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
