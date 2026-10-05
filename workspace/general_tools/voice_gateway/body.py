# Last updated: 2026-10-05 21:33:05
# @nova: Publish versioned voice state, captions and speech events for avatar and console subscribers.
#   what the voice is doing (state, captions, audio-clocked speech start/end, interruptions,
#   diagnostics). The gateway never drives a body itself; a body subscribes to this stream.
"""voice_gateway/body.py — v1 body events and the sinks that carry them.

Every event: {"v": 1, "seq": n, "ts": iso, "type": <kind>, ...}
    state       {state: idle|waiting|thinking|speaking, request_id?, message_id?, run_id?}
    caption     {text, message_id, request_id, run_id, unit, audit: {status, reason, source}, clock}
                emitted after playback API submission (clock "playback", not measured sound), or when the
                unit is handed over (clock "requested") for a backend that can't report it
    speech      {phase: requested|start|end, message_id, request_id, run_id, unit,
                 clock (start), outcome (end): played|completed|cut|skipped|no_audio|error}     mouth timing
    message     {phase: end|dropped, message_id?, request_id?, run_id?, delivery, audit?,
                 eligible, queued_units, why}   policy + queueing only; playback is in `speech`
    interrupt   {reason, dropped, cut_message_id, cut_unit}
    diagnostic  {level: info|warn|error, message}
A process-only backend reports completed with clock="process", without an audio-start caption.
Audit status travels with every caption: delivered is not approved, so a body can show
INCOMPLETE/ERROR/NOT_RUN instead of implying PASS. Lip-sync amplitude needs real audio (later).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class BodySink:
    def __init__(self):
        self._seq = 0

    def emit(self, kind: str, **fields) -> dict:
        self._seq += 1
        event = {"v": 1, "seq": self._seq, "ts": datetime.now().isoformat(timespec="milliseconds"),
                 "type": kind, **fields}
        try:
            self.write(event)
        except Exception as error:      # a broken body never breaks the voice
            print(f"[voice_gateway] body sink failed: {error}")
        return event

    def write(self, event: dict) -> None:
        pass

    def close(self) -> None:
        pass


class NullBody(BodySink):
    name = "none"


class MemoryBody(BodySink):
    """Keeps every event (tests, smoke runs)."""
    name = "memory"

    def __init__(self):
        super().__init__()
        self.events = []

    def write(self, event):
        self.events.append(event)

    def of(self, kind):
        return [e for e in self.events if e["type"] == kind]


class StdoutBody(BodySink):
    name = "stdout"

    def write(self, event):
        print("[body] " + json.dumps(event, ensure_ascii=False))


class JsonlBody(BodySink):
    """Appends events to a JSONL file a console can tail."""
    name = "jsonl"

    def __init__(self, path: Path):
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "a", encoding="utf-8", buffering=1)

    def write(self, event):
        self._file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def close(self):
        try:
            self._file.close()
        except Exception:
            pass


def make_body(cfg) -> BodySink:
    want = (getattr(cfg, "body_sink", "none") or "none").lower()
    if want == "stdout":
        return StdoutBody()
    if want == "jsonl":
        return JsonlBody(cfg.resolve(cfg.body_log_path))
    return NullBody()
