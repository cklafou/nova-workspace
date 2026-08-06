# Last updated: 2026-08-06 12:01:30
# @nova-adjacent: voice_gateway — configuration. All knobs in one place; overridable from
#   _admin/voice_gateway.json and env. No secrets here (there are none — this tool is local).
"""voice_gateway/config.py — every tunable for the gateway, with safe defaults."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

# workspace root = three levels up from this file (general_tools/voice_gateway/config.py)
WS_ROOT = Path(os.environ.get("NOVA_WORKSPACE", "")) or Path(__file__).resolve().parents[2]
_CFG_PATH = WS_ROOT / "_admin" / "voice_gateway.json"


@dataclass
class GatewayConfig:
    # ── transport: how we reach nova_chat (the EXISTING protocol, no server change) ────────
    nova_ws_url: str = "ws://127.0.0.1:8765/ws"
    speaker: str = "Cole"                 # whose voice the transcribed speech is attributed to

    # ── register: "text" (unchanged, full witness rounds), "voice" (rounds capped at 2),
    #    or "voice_fast" (rounds capped + reasoning skipped on casual first replies).
    #    Sent in the message payload; the server ignores it until the register patch is applied
    #    (see server_patch.md), so this is safe to set now. ────────────────────────────────
    register: str = "voice"

    # ── committer: when do we speak? "final" waits for the witness-approved message_end
    #    (SAFE default — nothing unaudited is spoken). "stream" speaks sentences as they
    #    generate (faster first audio, but pre-audit — only for voice_fast / casual). ────────
    speak_from: str = "final"             # "final" | "stream"
    min_chars: int = 7
    max_buffer: int = 220

    # ── STT / VAD (input) ─────────────────────────────────────────────────────────────────
    stt_backend: str = "moonshine"        # "moonshine" | "stdin" (stdin = type instead of talk)
    moonshine_model: str = "moonshine/base"   # or a local onnx dir
    vad_backend: str = "silero"           # "silero" | "none"
    vad_threshold: float = 0.5
    input_device: int = -1                # -1 = system default mic
    sample_rate: int = 16000
    silence_ms: int = 700                 # trailing silence that ends an utterance

    # ── TTS (output) ──────────────────────────────────────────────────────────────────────
    tts_backend: str = "auto"             # "auto" | "chatterbox" | "llamacpp" | "null"
    tts_reference_wav: str = ""           # Chatterbox zero-shot voice clone reference (~10s clip)
    tts_exaggeration: float = 0.6         # Chatterbox expressiveness (0..1); Cole: tomboyish/expressive
    tts_cfg_weight: float = 0.5
    llamacpp_tts_exe: str = "llama/llama-tts.exe"
    llamacpp_tts_model: str = ""          # a TTS gguf (e.g. OuteTTS) if using the llamacpp backend
    llamacpp_tts_vocoder: str = ""
    output_device: int = -1               # -1 = system default speakers

    # ── behavior ──────────────────────────────────────────────────────────────────────────
    barge_in: bool = True                 # stop speaking if Cole starts talking (needs full run)
    log_units: bool = True                # print each committed unit (observability, like pipeline)

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
        return p if p.is_absolute() else (WS_ROOT / p)
