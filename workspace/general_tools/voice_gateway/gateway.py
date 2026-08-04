#!/usr/bin/env python3
# Last updated: 2026-08-04 23:51:22
# @nova: voice_gateway — the pipe that lets Cole TALK to Nova. PLUCK TEST: this is a comms
#   tool, not a faculty. Remove it and Nova is unchanged — she still thinks, still audits, still
#   writes; she just has no microphone. Her body is untouched: the gateway only speaks nova_chat's
#   existing WebSocket protocol from the OUTSIDE, exactly as the browser UI does.
"""
voice_gateway/gateway.py — mic → Nova → speakers, with a smoke-test ladder so every layer can
be verified independently before the whole thing is wired to audio hardware.

THE SMOKE LADDER (run these in order as pieces come online):
  1. committer   python general_tools/voice_gateway/test_committer.py      (no deps)
  2. link        python general_tools/voice_gateway/gateway.py --smoke-link "hey nova, what's up"
                 → connects to a RUNNING Nova, sends the text as Cole, prints her streamed reply
                   and the sentence units the committer would speak. Proves the transport + the
                   committer end-to-end with NO audio stack.
  3. tts         python general_tools/voice_gateway/gateway.py --smoke-tts "This is my voice test."
                 → runs text through the committer into the configured TTS backend (Null logs;
                   Chatterbox/llamacpp actually speak).
  4. run         python general_tools/voice_gateway/gateway.py --run
                 → full loop. With stt_backend='stdin' you TYPE to her and hear her reply — the
                   whole gateway, testable before a microphone is ever configured.

Config: general_tools/voice_gateway/config.py (+ _admin/voice_gateway.json). See README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from committer import SentenceCommitter, commit_block   # noqa: E402
from config import GatewayConfig                          # noqa: E402


def _claim_gate():
    """Wire the committer's claim tag to Nova's OWN claim detector if her body is importable
    (read-only use of a faculty — the pluck test still holds; we depend on nothing). Falls back
    to None (no tagging) so the gateway runs standalone."""
    try:
        sys.path.insert(0, str(GatewayConfig.load().resolve("nova_body")))
        from nova_cortex import witness as w
        return lambda text: bool(w.needs_witness(text, asked=False))
    except Exception:
        return None


# ── mode 2: link smoke — transport + committer, no audio ─────────────────────────────────────
async def smoke_link(cfg: GatewayConfig, text: str):
    from nova_link import NovaLink
    committer = SentenceCommitter(min_chars=cfg.min_chars, max_buffer=cfg.max_buffer,
                                  claim_gate=_claim_gate())
    print(f"[voice_gateway] → Nova ({cfg.register}): {text!r}\n")
    async with NovaLink(cfg.nova_ws_url, cfg.speaker, cfg.register) as link:
        await link.say(text)
        async for kind, payload in link.replies():
            if kind == "start":
                print("[voice_gateway] Nova is answering…")
            elif kind == "token" and cfg.speak_from == "stream":
                for u in committer.feed(payload):
                    _show_unit(u)
            elif kind == "end":
                if cfg.speak_from == "stream":
                    for u in committer.flush():
                        _show_unit(u)
                else:
                    print(f"\n[voice_gateway] full reply ({len(payload)} chars); "
                          f"committing to speech units:\n")
                    for u in commit_block(payload, min_chars=cfg.min_chars,
                                          max_buffer=cfg.max_buffer, claim_gate=_claim_gate()):
                        _show_unit(u)
                print("\n[voice_gateway] done.")
                return
            elif kind == "error":
                print(f"[voice_gateway] Nova error: {payload}")
                return


# ── mode 3: tts smoke — committer + TTS backend, no transport ────────────────────────────────
def smoke_tts(cfg: GatewayConfig, text: str):
    from tts import make_tts
    tts = make_tts(cfg)
    print(f"[voice_gateway] TTS backend: {tts.name}")
    for u in commit_block(text, min_chars=cfg.min_chars, max_buffer=cfg.max_buffer):
        tts.speak(u.text)
    tts.close()


# ── mode 4: full run — STT → Nova → committer → TTS ──────────────────────────────────────────
async def run(cfg: GatewayConfig):
    from nova_link import NovaLink
    from stt import make_stt
    from tts import make_tts

    stt = make_stt(cfg)
    tts = make_tts(cfg)
    gate = _claim_gate()
    print(f"[voice_gateway] STT={stt.name}  TTS={tts.name}  register={cfg.register}  "
          f"speak_from={cfg.speak_from}")

    async with NovaLink(cfg.nova_ws_url, cfg.speaker, cfg.register) as link:
        async def _speak_replies():
            committer = SentenceCommitter(min_chars=cfg.min_chars, max_buffer=cfg.max_buffer,
                                          claim_gate=gate)
            async for kind, payload in link.replies():
                if kind == "token" and cfg.speak_from == "stream":
                    for u in committer.feed(payload):
                        _emit(cfg, tts, u)
                elif kind == "end":
                    units = (committer.flush() if cfg.speak_from == "stream"
                             else commit_block(payload, min_chars=cfg.min_chars,
                                               max_buffer=cfg.max_buffer, claim_gate=gate))
                    for u in units:
                        _emit(cfg, tts, u)
                elif kind == "error":
                    print(f"[voice_gateway] Nova error: {payload}")

        speaker_task = asyncio.ensure_future(_speak_replies())
        try:
            async for utt in stt.utterances():
                print(f"[voice_gateway] Cole: {utt}")
                await link.say(utt)
        finally:
            speaker_task.cancel()
            stt.close()
            tts.close()


def _emit(cfg, tts, unit):
    if cfg.log_units:
        _show_unit(unit)
    tts.speak(unit.text)


def _show_unit(u):
    tag = " [claim]" if getattr(u, "is_claim", False) else ""
    soft = " (soft)" if getattr(u, "soft", False) else ""
    print(f"  » {u.text}{tag}{soft}")


def main():
    ap = argparse.ArgumentParser(description="Nova voice gateway")
    ap.add_argument("--smoke-link", metavar="TEXT", help="send TEXT to a running Nova, print reply+units")
    ap.add_argument("--smoke-tts", metavar="TEXT", help="run TEXT through committer+TTS")
    ap.add_argument("--run", action="store_true", help="full loop: STT → Nova → committer → TTS")
    args = ap.parse_args()
    cfg = GatewayConfig.load()

    if args.smoke_link is not None:
        asyncio.run(smoke_link(cfg, args.smoke_link))
    elif args.smoke_tts is not None:
        smoke_tts(cfg, args.smoke_tts)
    elif args.run:
        asyncio.run(run(cfg))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
