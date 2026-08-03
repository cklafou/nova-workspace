#!/usr/bin/env python3
# Last updated: 2026-08-03 22:25:53
# @nova: CLOUD LANES transport (lane 1: witness-heavy). A stateless organ-for-hire caller —
#        request out, verdict back, nothing of Nova persists in the cloud. FAIL-OPEN by law:
#        unreachable, over deadline, over budget, or disabled -> CloudSkip, logged loudly,
#        and the caller continues local. Plan: memory/reports/CLOUD_LANES_2026-08-02.md
"""
general_tools/cloud_call.py — the one door to the cloud.

Config lives in nova_config.json (finally wired, per WIRING.md's orphan note):

    "cloud": {
        "enabled": true,                     <- the kill switch. false = pre-cloud Nova, exactly.
        "monthly_cap_usd": 25,
        "lanes": {
            "witness_heavy": {
                "base_url": "https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1",
                "model": "nova-witness-heavy",
                "api_key_env": "RUNPOD_API_KEY",   <- env var name (checked first)
                "api_key_file": "models/witness/APILargeWitness.txt",  <- fallback: file holding
                                   the key (models/ is gitignored and sealed to her tools)
                "deadline_s": 90,
                "est_cost_per_call_usd": 0.008
            }
        }
    }

Usage (the heavy witness, from anywhere in the stack):

    from cloud_call import cloud_chat, CloudSkip
    try:
        verdict = cloud_chat("witness_heavy", messages, max_tokens=2048)
    except CloudSkip as e:
        ...  # the inline verdict stands; e.reason says why (also in pipeline.jsonl)

Every call and every skip is a pipeline event (cloud_call / cloud_skip) with lane, latency,
and estimated cost, and the ledger (memory/cloud_ledger.json) accumulates monthly spend so
the cap is enforced and Nova can read her own body's bill.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

_WS = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
       else Path(__file__).resolve().parent.parent)
_CONFIG_PATH = _WS / "nova_config.json"
_LEDGER_PATH = _WS / "memory" / "cloud_ledger.json"


class CloudSkip(Exception):
    """The cloud didn't answer in budget/deadline/policy — continue local. Never fatal."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _pipeline_event(stage: str, what: str, **fields) -> None:
    try:
        from nova_cortex import witness as _w
        _w.pipeline_event(stage, what, **fields)
    except Exception:
        try:
            print(f"[cloud_call] {stage}: {what}")
        except Exception:
            pass


def _config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8")).get("cloud", {})
    except Exception:
        return {}


def _ledger_read() -> dict:
    try:
        return json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ledger_add(lane: str, est_usd: float) -> None:
    """Best-effort monthly accounting. Atomic write; never raises."""
    try:
        month = datetime.now().strftime("%Y-%m")
        led = _ledger_read()
        if led.get("month") != month:
            led = {"month": month, "lanes": {}}
        ln = led["lanes"].setdefault(lane, {"calls": 0, "est_usd": 0.0})
        ln["calls"] += 1
        ln["est_usd"] = round(ln["est_usd"] + est_usd, 6)
        ln["last_ts"] = datetime.now().isoformat(timespec="seconds")
        tmp = _LEDGER_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(led, indent=1), encoding="utf-8")
        os.replace(tmp, _LEDGER_PATH)
    except Exception:
        pass


def _served_model(base_url: str, api_key: str, timeout: float = 15) -> str:
    """Best-effort: what model does the endpoint actually serve? Avoids a name-mismatch 404
    when a RunPod served-name override wasn't set. Empty on any failure (caller falls back).
    Doubles as the reachability PING (Cole, 2026-08-03): a short timeout means a cold or
    unreachable endpoint returns '' fast instead of hanging the dispute on a dead socket."""
    try:
        req = urllib.request.Request(base_url + "/models",
                                     headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
        return ids[0] if ids else ""
    except Exception:
        return ""


def _get_api_key(lane_cfg: dict) -> str:
    """Env var first (never logged), then the key file (path relative to the workspace).
    The file lives in models/ on purpose: gitignored for size, SEALED to Nova's own tools —
    the key never syncs and she never reads it."""
    key = os.environ.get(lane_cfg.get("api_key_env", "") or "", "")
    if key:
        return key.strip()
    kf = lane_cfg.get("api_key_file", "")
    if kf:
        try:
            return (_WS / kf).read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def _month_spend(led: dict) -> float:
    return round(sum(l.get("est_usd", 0.0) for l in led.get("lanes", {}).values()), 4)


def cloud_chat(lane: str, messages: list, max_tokens: int = 2048,
               temperature: float = 0.2, top_p: float = 0.9,
               deadline_s: float | None = None) -> str:
    """One chat completion through a cloud lane. Returns the reply text, or raises CloudSkip.

    N0 rule (CLOUD_LANES): callers must not put Cole's health/personal data in `messages`.
    The witness payload (draft + wire excerpts + receipts) is class N1, blessed 2026-08-02.
    """
    cfg = _config()
    if not cfg.get("enabled", False):
        raise CloudSkip("cloud disabled (nova_config.json cloud.enabled=false)")
    lane_cfg = (cfg.get("lanes") or {}).get(lane)
    if not lane_cfg:
        raise CloudSkip(f"no config for lane '{lane}'")
    api_key = _get_api_key(lane_cfg)
    if not api_key:
        raise CloudSkip("no api key: env '%s' unset and file '%s' unreadable" % (
            lane_cfg.get("api_key_env", ""), lane_cfg.get("api_key_file", "")))

    cap = float(cfg.get("monthly_cap_usd", 0) or 0)
    est = float(lane_cfg.get("est_cost_per_call_usd", 0.01) or 0.01)
    led = _ledger_read()
    if cap and led.get("month") == datetime.now().strftime("%Y-%m") and \
            _month_spend(led) + est > cap:
        _pipeline_event("cloud_skip", f"lane {lane}: monthly cap ${cap} reached — running local",
                        lane=lane, reason="over_budget")
        raise CloudSkip(f"monthly cap ${cap} reached")

    base = lane_cfg["base_url"].rstrip("/")
    url = base + "/chat/completions"
    # ── PING-VERIFIED ESCALATION (Cole, 2026-08-03, turnabout Q1) ──
    # Ping the endpoint FIRST (GET /models) with a short timeout. No confirmed receipt in
    # time — cold serverless worker, no route, dead lane — and we SKIP IMMEDIATELY instead
    # of hanging the dispute on a 90s socket. Only a confirmed receipt earns the ~8s wait
    # for the ruling (Cole's number); the caller may override via deadline_s. On any skip
    # Nova stays the final authority (the consensus turn), so failing fast is always safe.
    _ping_to = float(lane_cfg.get("ping_timeout_s", 4))
    model_name = _served_model(base, api_key, timeout=_ping_to)
    if not model_name:
        _pipeline_event("cloud_skip",
                        f"lane {lane}: ping unanswered in {_ping_to:.0f}s — not reachable "
                        f"in time, skipping now (fail-open)",
                        lane=lane, reason="ping_no_receipt")
        raise CloudSkip(f"ping unanswered in {_ping_to:.0f}s")
    deadline = float(deadline_s or lane_cfg.get("wait_s", 8))
    payload = {"model": model_name, "messages": messages,
               "max_tokens": max_tokens, "temperature": temperature, "top_p": top_p,
               "stream": False, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {api_key}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=deadline) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        if not text:
            raise ValueError("empty completion")
    except CloudSkip:
        raise
    except Exception as e:
        _pipeline_event("cloud_skip",
                        f"lane {lane}: {type(e).__name__} after {time.time()-t0:.1f}s — "
                        f"continuing local (fail-open)",
                        lane=lane, reason=str(e)[:200])
        raise CloudSkip(f"{type(e).__name__}: {e}") from e

    dt = time.time() - t0
    _ledger_add(lane, est)
    _pipeline_event("cloud_call",
                    f"lane {lane}: verdict in {dt:.1f}s (~${est:.3f}; month so far "
                    f"${_month_spend(_ledger_read()):.2f})",
                    lane=lane, latency_s=round(dt, 2), est_usd=est)
    return text


_HEAVY_LOG_DIR = _WS / "logs" / "heavy_witness"


def _log_heavy(messages: list, response: str, meta: dict | None = None) -> None:
    """Write the FULL cloud exchange — the exact payload sent and the exact reply — to
    logs/heavy_witness/YYYY-MM-DD.jsonl. (Cole, 2026-08-03: 'A blind uninformed witness is
    useless... there should always be a payload with full context, and I need to see what was
    sent and what they said.') The pipeline event is the headline; THIS is the receipt. Never
    raises."""
    try:
        _HEAVY_LOG_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now().strftime("%Y-%m-%d")
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            # the system + user messages EXACTLY as the cloud judge received them
            "payload": [{"role": m.get("role"), "content": str(m.get("content", ""))[:12000]}
                        for m in (messages or [])],
            "response": str(response or "")[:8000],
        }
        if meta:
            rec.update(meta)
        with open(_HEAVY_LOG_DIR / f"{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def heavy_witness(draft: str, turn_tools: list, history: list | None = None,
                  thinking: str = "", prior_concern: str = "",
                  checks: list | None = None, has_image: bool = False) -> str:
    """The deferred-lane heavy witness — the INFORMED arbiter (Cole, 2026-08-03). It gets the
    context-RICH prompt (build_heavy_witness: the conversation record + tool activity the fast
    local witness lacked) so it can actually RULE instead of blindly asking to read. Judged by
    her own base model (no persona LoRA) in the cloud. Every exchange — the full payload and the
    full reply — is written to logs/heavy_witness/. Returns the raw verdict; raises CloudSkip on
    any failure (the inline verdict simply stands)."""
    from nova_cortex import witness as _w
    messages = _w.build_heavy_witness(draft, turn_tools, history=history, thinking=thinking,
                                      prior_concern=prior_concern, checks=checks,
                                      has_image=has_image)
    resp = cloud_chat("witness_heavy", messages, max_tokens=2048)
    _log_heavy(messages, resp)
    return resp


if __name__ == "__main__":
    # Smoke test: python general_tools/cloud_call.py  (needs RUNPOD_API_KEY set)
    try:
        out = cloud_chat("witness_heavy",
                         [{"role": "system", "content": "You are a strict auditor."},
                          {"role": "user", "content": "Reply with exactly: PASS"}],
                         max_tokens=8)
        print("cloud says:", out)
    except CloudSkip as e:
        print("skipped (fail-open works):", e.reason)
