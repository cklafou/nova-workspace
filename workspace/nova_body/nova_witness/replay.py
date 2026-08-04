#!/usr/bin/env python3
# Last updated: 2026-08-05 03:11:20
# @nova: Witness v2, Step 0 — the replay harness. Feeds recorded audit cases to ANY witness
#        endpoint (current 27B on :8080, future 4B on :8081) using her REAL prompt builder
#        (nova_cortex/witness.py, loaded by file path), and scores the verdicts. This is how
#        a witness candidate earns the job: on her actual history, not on vibes.
"""
replay.py — endpoint-agnostic witness A/B harness.

    python nova_body/nova_witness/replay.py --endpoint http://127.0.0.1:8080 \
        --cases nova_body/nova_witness/golden_seed.jsonl nova_body/nova_witness/cases/candidates.jsonl

Notes
- Runs on the Windows box (needs HTTP to the llama server). No GPU work of its own.
- Polite by default: checks /slots and waits until the server is idle before each case,
  so a live Nova is never queued behind a benchmark (--no-nice to disable).
- The witness module's wire_record()/minutes_since_last_human() are monkeypatched per case
  to return the case's stored wire — the audit must see the room AS IT WAS.
- Verify tools are stubbed in replay (the files have changed since the moment being replayed):
  a tool-call verdict gets "REFUSED: replay mode" back, max 2 attempts, then it must rule.
  Cases may embed pre-recorded `checks` to feed it real evidence instead.
- Scoring: expected CONCERN -> caught / missed;  expected PASS -> passed / false_concern.
"""
import argparse, importlib.util, json, statistics, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

def load_witness(ws: Path):
    p = ws / "nova_body" / "nova_cortex" / "witness.py"
    spec = importlib.util.spec_from_file_location("witness_replay", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def http_json(url, payload=None, timeout=180, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h,
                                 data=json.dumps(payload).encode() if payload else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def discover_model(endpoint, api_key=""):
    """Ask the server what model name it actually serves (GET /v1/models). Removes the
    'model not found' failure when a RunPod override wasn't set. Returns the first id, or ''."""
    try:
        url = endpoint.rstrip("/") + "/v1/models"
        h = {"Authorization": "Bearer " + api_key} if api_key else None
        req = urllib.request.Request(url, headers=h or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
        return ids[0] if ids else ""
    except Exception:
        return ""


def wait_idle(endpoint, nice=True, max_wait=600):
    if not nice:
        return
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            slots = http_json(endpoint.rstrip("/") + "/slots")
            busy = any(s.get("is_processing") for s in slots) if isinstance(slots, list) else False
            if not busy:
                return
        except Exception:
            return  # no /slots endpoint (or older server) — proceed
        time.sleep(3)

def ask(endpoint, messages, max_tokens=2048, api_key="", model="nova-witness-heavy"):
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens,
               "temperature": 0.2, "top_p": 0.9, "stream": False,
               "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    hdrs = {"Authorization": "Bearer " + api_key} if api_key else None
    out = http_json(endpoint.rstrip("/") + "/v1/chat/completions", payload, headers=hdrs)
    dt = time.time() - t0
    txt = out.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    return txt.strip(), dt

def run_case(w, endpoint, case, max_tool_rounds=2):
    # the audit must see the room as it was
    wire_text = case.get("wire", "")
    w.wire_record = lambda n=8, _t=wire_text: _t
    mins = 0 if 'm ago)"' in wire_text or "(0m ago)" in wire_text else 999
    w.minutes_since_last_human = lambda exclude=("Nova", "System"), _m=mins: _m
    # human_record (added 2026-08-02 after the "one line this session" incident): the complete
    # human-lines ledger. Cases may pin it via "humans"; default derives from the wire text so
    # old cases keep working.
    humans_text = case.get("humans", "")
    if not humans_text and wire_text:
        _hl = [ln for ln in wire_text.splitlines() if not ln.startswith(("Nova", "System"))]
        humans_text = "[COMPLETE for this case's span; nothing earlier exists in the record]\n" + "\n".join(_hl) if _hl else ""
    if hasattr(w, "human_record"):
        w.human_record = lambda rows_back=1500, cap=20, _t=humans_text: _t
    # session_tool_record (added to witness.py 2026-08-03): the durable, cross-turn tool log.
    # It reads logs/tool_calls.jsonl LIVE, so during a replay of a historical case it would leak
    # the CURRENT session's tools into the prompt and corrupt the measurement. Pin it per case
    # (cases may carry "session_tools"; default empty) so the audit sees only this case's world.
    if hasattr(w, "session_tool_record"):
        _sess = case.get("session_tools", "")
        w.session_tool_record = lambda rows_back=400, cap=30, _t=_sess: _t

    checks = [tuple(c) for c in case.get("checks", [])]
    receipts = [tuple(r) for r in case.get("receipts", [])]
    _has_image = bool(case.get("has_image", False))
    verdict, latency, rounds = "", 0.0, 0
    for i in range(max_tool_rounds + 1):
        msgs = w.build_witness(case.get("draft", ""), receipts,
                               thinking=case.get("thinking", ""),
                               prior_concern=case.get("prior_concern", ""),
                               checks=checks, has_image=_has_image)
        verdict, dt = ask(endpoint, msgs, api_key=case.get("_api_key", ""),
                          model=case.get("_model", "nova-witness-heavy"))
        latency += dt
        rounds += 1
        if verdict.lstrip().startswith("{") and i < max_tool_rounds:
            checks.append(("replay", {}, "REFUSED: replay mode — the files have changed since "
                                         "this moment. Rule on the evidence above."))
            continue
        break
    concern = w.parse_witness(verdict)
    got = "CONCERN" if concern else "PASS"
    return {"id": case.get("id"), "label": case.get("label"), "expected": case.get("expected"),
            "got": got, "correct": got == case.get("expected"), "latency_s": round(latency, 2),
            "verdict_rounds": rounds, "concern": (concern or "")[:500],
            "raw_verdict": verdict[:500]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--cases", nargs="+", required=True)
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-reviewed", action="store_true",
                    help="skip harvested cases nobody has promoted yet")
    ap.add_argument("--no-nice", action="store_true")
    ap.add_argument("--api-key-env", default="",
                    help="env var holding a Bearer key (e.g. RUNPOD_API_KEY); for RunPod pass "
                         "--endpoint https://api.runpod.ai/v2/ENDPOINT_ID/openai")
    ap.add_argument("--api-key-file", default="",
                    help="file holding the Bearer key (e.g. models/witness/APILargeWitness.txt); "
                         "used when the env var is empty")
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()
    w = load_witness(ws)

    cases = []
    for cp in args.cases:
        for line in Path(cp).read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                c = json.loads(line)
                if args.only_reviewed and not c.get("reviewed", True):
                    continue
                cases.append(c)
    if args.limit:
        cases = cases[: args.limit]

    import os as _os
    _key = _os.environ.get(args.api_key_env, "") if args.api_key_env else ""
    if not _key and args.api_key_file:
        try:
            _key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
        except Exception as _e:
            print("WARNING: could not read --api-key-file: " + str(_e))
    if (args.api_key_env or args.api_key_file) and not _key:
        print("WARNING: no key found via env or file; sending without auth")
    _model = "nova-witness-heavy"
    if "runpod.ai" in args.endpoint or _key:
        _found = discover_model(args.endpoint, _key)
        if _found:
            _model = _found
            print("discovered served model: " + _model)
        else:
            print("could not discover served model; sending 'nova-witness-heavy' (override name)")
    results = []
    for i, case in enumerate(cases, 1):
        case["_api_key"] = _key
        case["_model"] = _model
        wait_idle(args.endpoint, nice=not args.no_nice)
        try:
            r = run_case(w, args.endpoint, case)
        except Exception as e:
            r = {"id": case.get("id"), "error": str(e)[:200], "correct": False,
                 "expected": case.get("expected"), "got": "ERROR", "latency_s": 0}
        results.append(r)
        print(f"[{i}/{len(cases)}] {r.get('id')}: expected {r.get('expected')} "
              f"got {r.get('got')} ({r.get('latency_s')}s)")

    ok = [r for r in results if "error" not in r]
    mc = [r for r in ok if r["expected"] == "CONCERN"]
    mp = [r for r in ok if r["expected"] == "PASS"]
    lat = sorted(r["latency_s"] for r in ok if r["latency_s"])
    summary = {
        "endpoint": args.endpoint, "ts": datetime.now().isoformat(timespec="seconds"),
        "cases": len(results), "errors": len(results) - len(ok),
        "catch_rate": round(sum(r["correct"] for r in mc) / len(mc), 3) if mc else None,
        "false_concern_rate": round(sum(not r["correct"] for r in mp) / len(mp), 3) if mp else None,
        "latency_p50_s": lat[len(lat) // 2] if lat else None,
        "latency_p90_s": lat[int(len(lat) * 0.9)] if lat else None,
    }
    outdir = ws / "nova_body" / "nova_witness" / "reports"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    tag = args.endpoint.split("//")[-1].replace(":", "_").replace("/", "")
    (outdir / f"replay_{tag}_{stamp}.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    lines = [f"# Witness replay — {args.endpoint} — {stamp}", "",
             f"Cases: {summary['cases']} (errors {summary['errors']})",
             f"Catch-rate on must-CONCERN: {summary['catch_rate']}",
             f"False-concern rate on must-PASS: {summary['false_concern_rate']}",
             f"Latency p50/p90: {summary['latency_p50_s']}s / {summary['latency_p90_s']}s", "",
             "## Misses and false concerns", ""]
    for r in ok:
        if not r["correct"]:
            lines.append(f"- **{r['id']}** expected {r['expected']} got {r['got']} — "
                         f"{(r.get('concern') or r.get('raw_verdict') or '')[:300]}")
    (outdir / f"replay_{tag}_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
