# @nova: Configure detachable voice input, playback, audit policy and body-event outputs.
# Last updated: 2026-10-06 03:19:20
#   _admin/voice_gateway.json and env. No secrets here (there are none — this tool is local).
"""voice_gateway/config.py — every tunable for the gateway, with safe defaults."""
from __future__ import annotations

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "nova_body"))
from nova_paths import WORKSPACE_ROOT, workspace_path

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

# workspace root = three levels up from this file (general_tools/voice_gateway/config.py)
WS_ROOT = WORKSPACE_ROOT
_CFG_PATH = WS_ROOT / "_admin" / "voice_gateway.json"


@dataclass
class GatewayConfig:
    # ── transport: how we reach nova_chat (the EXISTING protocol, no server change) ────────
    nova_ws_url: str = "ws://127.0.0.1:8765/ws"
    speaker: str = "Cole"                 # whose voice the transcribed speech is attributed to

    # ── register: "text", "voice" or "voice_fast", sent with every utterance. Nova Chat validates
    #    it per request (2026-10-05 contract); it never switches a human request into autonomous mode.
    register: str = "voice_fast"

    # ── speech policy (first stage). Only text Nova Chat DELIVERED is spoken; delivered is not
    #    the same as witness-approved, so the audit status rides along on every caption.
    speak_from: str = "final"             # first stage: "final" only ("stream" is ignored, with a warning)
    speak_scope: str = "mine"             # "mine" = replies to this gateway's own request_ids;
                                          # "replies" = any delivered reply to a human line (reply_to set)
    audit_gate: str = "delivered"         # "delivered": speak any delivered reply, its audit status attached;
                                          # "pass_only": speak only an explicit PASS (NOT_RUN stays silent)
    request_timeout_s: int = 300          # expire unacknowledged requests; flag current accepted turn as delayed
    min_chars: int = 7
    max_buffer: int = 220

    # ── STT / VAD (input) ─────────────────────────────────────────────────────────────────
    stt_backend: str = "faster_whisper"   # "faster_whisper" | "moonshine" | "stdin"
    whisper_model: str = "large-v3-turbo"  # prepared local CTranslate2 directory or bundled model
    speech_language: str = "en"          # Cole speaks English; explicit language avoids short-clip guesses
    whisper_cpu_threads: int = 8          # CPU int8 keeps Nova's occupied GPUs available
    moonshine_model: str = "moonshine/base"   # or a local onnx dir
    vad_backend: str = "silero"           # "silero" | "none"
    vad_threshold: float = 0.5
    input_device: int = -1                # -1 = system default mic
    sample_rate: int = 16000
    silence_ms: int = 2000                # natural pause before finalizing; continuation during decode joins the turn
    min_speech_ms: int = 192              # ignore isolated VAD spikes before decoding
    pre_roll_ms: int = 288                # retain speech onset before VAD fires
    speech_tail_ms: int = 192             # trim long terminal silence before decoding

    # ── TTS (output) ──────────────────────────────────────────────────────────────────────
    tts_backend: str = "auto"             # "auto" | "windows" | "chatterbox" | "llamacpp" | "null"
    windows_voice: str = ""              # exact installed System.Speech voice name; empty = installed English female voice when available
    tts_reference_wav: str = ""           # Chatterbox zero-shot voice clone reference (~10s clip)
    tts_exaggeration: float = 0.6         # Chatterbox expressiveness (0..1); Cole: tomboyish/expressive
    tts_cfg_weight: float = 0.5
    llamacpp_tts_exe: str = "llama/llama-tts.exe"
    llamacpp_tts_model: str = ""          # a TTS gguf (e.g. OuteTTS) if using the llamacpp backend
    llamacpp_tts_vocoder: str = ""
    output_device: int = -1               # -1 = system default speakers

    # ── behavior ──────────────────────────────────────────────────────────────────────────
    duplex: str = "half"                  # "half": the mic is ignored while she speaks (+ tail), so her
                                          # voice is never transcribed as Cole's; "full": headphones/AEC
    half_duplex_tail_ms: int = 400
    barge_in: bool = True                 # full duplex only: Cole starting to talk stops her speech
    body_sink: str = "none"               # "none" | "stdout" | "jsonl" — v1 body events (see body.py)
    body_log_path: str = "logs/voice/body_events.jsonl"
    log_units: bool = True                # print each unit as it is spoken

    @classmethod
    def load(cls) -> "GatewayConfig":
        cfg = cls()
        # file overrides
        try:
            if _CFG_PATH.exists():
                data = json.loads(_CFG_PATH.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
        except Exception as e:
            print(f"[voice_gateway] config file ignored ({e}); using defaults")
        # env overrides (VOICE_GW_<FIELD>)
        for k in asdict(cfg):
            env = os.environ.get("VOICE_GW_" + k.upper())
            if env is not None:
                cur = getattr(cfg, k)
                try:
                    if isinstance(cur, bool):
                        setattr(cfg, k, env.strip().lower() in ("1", "true", "yes", "on"))
                    elif isinstance(cur, int):
                        setattr(cfg, k, int(env))
                    elif isinstance(cur, float):
                        setattr(cfg, k, float(env))
                    else:
                        setattr(cfg, k, env)
                except Exception:
                    pass
        return cfg

    def resolve(self, rel: str) -> Path:
        """Resolve a possibly-relative path against the workspace root."""
        p = Path(rel)
        return workspace_path(p, workspace=WS_ROOT)
