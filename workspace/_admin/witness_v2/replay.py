#!/usr/bin/env python3
# Last updated: 2026-08-02 13:14:50
# @nova: Witness v2, Step 0 — the replay harness. Feeds recorded audit cases to ANY witness
#        endpoint (current 27B on :8080, future 4B on :8081) using her REAL prompt builder
#        (nova_cortex/witness.py, loaded by file path), and scores the verdicts. This is how
#        a witness candidate earns the job: on her actual history, not on vibes.
"""
replay.py — endpoint-agnostic witness A/B harness.

    python _admin/witness_v2/replay.py --endpoint http://127.0.0.1:8080 \
        --cases _admin/witness_v2/golden_seed.jsonl _admin/witness_v2/cases/candidates.jsonl

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

def http_json(url, payload=None, timeout=180):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

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

def ask(endpoint, messages, max_tokens=2048):
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.2,
               "top_p": 0.9, "stream": False,
               "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    out = http_json(endpoint.rstrip("/") + "/v1/chat/completions", payload)
    dt = time.time() - t0
    txt = out.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    return txt.strip(), dt

def run_case(w, endpoint, case, max_tool_rounds=2):
    # the audit must see the room as it was
    wire_text = case.get("wire", "")
    w.wire_record = lambda n=8, _t=wire_text: _t
    mins = 0 if 'm ago)"' in wire_text or "(0m ago)" in wire_text else 999
    w.minutes_since_last_human = lambda exclude=("Nova", "System"), _m=mins: _m

    checks = [tuple(c) for c in case.get("checks", [])]
    receipts = [tuple(r) for r in case.get("receipts", [])]
    verdict, latency, rounds = "", 0.0, 0
    for i in range(max_tool_rounds + 1):
        msgs = w.build_witness(case.get("draft", ""), receipts,
                               thinking=case.get("thinking", ""),
                               prior_concern=case.get("prior_concern", ""),
                               checks=checks)
        verdict, dt = ask(endpoint, msgs)
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

    results = []
    for i, case in enumerate(cases, 1):
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
    outdir = ws / "_admin" / "witness_v2" / "reports"
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
