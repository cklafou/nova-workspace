# Last updated: 2026-10-05 21:33:05
# @nova: Capture bounded opt-in provider payloads and phase timings in disposable Temp diagnostics without changing generation.
"""Local debugging only. No capture without a short-lived explicit marker; never image pixels."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2] / "Temp" / "provider-diagnostics"
MAX_FILES = 32
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024


def _target():
    marker = ROOT / "capture.json"
    if not marker.exists() or marker.stat().st_size > 4096:
        return None
    config = json.loads(marker.read_text(encoding="utf-8"))
    name = config.get("capture_id", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        return None
    until = datetime.fromisoformat(config["expires_at"])
    if until.tzinfo is None or not 0 < (until - datetime.now(timezone.utc)).total_seconds() <= 600:
        return None
    return ROOT / name


def _write(path, record):
    data = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    files = list(path.parent.glob("*.json"))
    if (path not in files and len(files) >= MAX_FILES
            or sum(p.stat().st_size for p in files if p != path) + len(data) > MAX_TOTAL_BYTES):
        return False
    temp = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, suffix='.tmp', delete=False) as f:
            temp = f.name
            f.write(data)
        os.replace(temp, path)
        return True
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def _run_id():
    from nova_runtime.operations import current_operation
    operation = current_operation.get()
    return operation.id if operation else None


def _without_pixels(value):
    if isinstance(value, dict):
        return {key: _without_pixels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_without_pixels(item) for item in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        return value.split(";", 1)[0] + ";[pixels omitted]"
    return value


def _hash(value):
    digest = hashlib.sha256()
    for piece in json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":")).iterencode(value):
        digest.update(piece.encode("utf-8"))
    return digest.hexdigest()


def begin(payload, *, phase):
    """Snapshot the final JSON fields given to HTTPX, after fitting; disabled by default."""
    try:
        directory = _target()
        if directory is None:
            return None
        from nova_cortex.context_budget import _current_request, content_text
        messages = payload.get("messages", [])
        request_index = _current_request(messages)
        request = content_text(messages[request_index].get("content")) if request_index is not None else ""
        record = {"@nova": "Opt-in local provider request/timing receipt; image bytes omitted.",
                  "started_at": datetime.now(timezone.utc).isoformat(), "run_id": _run_id(),
                  "phase": phase, "status": "started", "payload": _without_pixels(payload),
                  "canonical_payload_sha256": _hash(payload),
                  "payload_scope": "Exact outgoing JSON fields, except image data URLs are replaced; not raw HTTP bytes.",
                  "current_request_index": request_index, "current_request_sha256": _hash(request),
                  "message_text_chars": [len(content_text(m.get("content"))) for m in messages]}
        path = directory / (uuid.uuid4().hex + ".json")
        if not _write(path, record):
            return None
        return ProviderTrace(path, record)
    except Exception:
        return None  # A diagnostic never becomes a generation dependency.


class ProviderTrace:
    def __init__(self, path, record):
        self.path, self.record = path, record
        self.started = time.perf_counter()
        self.first_token_ms = self.first_content_ms = None
        self.token_chars = self.think_chars = 0

    def chunk(self, chunk):
        try:
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            content, thinking = delta.get("content") or "", delta.get("reasoning_content") or ""
            elapsed = round((time.perf_counter() - self.started) * 1000, 2)
            if (content or thinking) and self.first_token_ms is None:
                self.first_token_ms = elapsed
            if content and self.first_content_ms is None:
                self.first_content_ms = elapsed
            self.token_chars += len(content)
            self.think_chars += len(thinking)
            for key in ("usage", "timings"):
                values = chunk.get(key)
                if isinstance(values, dict):
                    self.record[key] = {k: v for k, v in values.items()
                                        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
            if choice.get("finish_reason"):
                self.record["finish_reason"] = str(choice["finish_reason"])[:80]
        except Exception:
            pass

    def finish(self, status):
        try:
            self.record.update(status=status, elapsed_ms=round((time.perf_counter() - self.started) * 1000, 2),
                               first_token_ms=self.first_token_ms, first_content_ms=self.first_content_ms,
                               content_chars=self.token_chars, thinking_chars=self.think_chars)
            _write(self.path, self.record)
        except Exception:
            pass


def record_phase(phase, started, **identity):
    """Measure server context preparation independently of provider and speech latency."""
    try:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        directory = _target()
        if directory is not None:
            _write(directory / (uuid.uuid4().hex + ".json"), {
                "@nova": "Opt-in context assembly timing; contains no prompt text.",
                "phase": phase, "run_id": _run_id(), "elapsed_ms": elapsed_ms,
                "recorded_at": datetime.now(timezone.utc).isoformat(), **identity})
    except Exception:
        pass
