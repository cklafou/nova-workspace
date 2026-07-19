#!/usr/bin/env python3
"""
MTP correctness A/B — is llama.cpp's draft-mtp lossless on THIS build, with HER adapter?

WHY THIS EXISTS
    Speculative decoding is supposed to be mathematically lossless: the draft head proposes,
    the target model verifies, and the committed token stream is EXACTLY what the target would
    have produced alone. Speed changes; output must not.

    On Qwen3.6 MTP that guarantee is broken — see ggml-org/llama.cpp issues #23302 and #23335.
    The decisive evidence in #23335: at --spec-draft-n-max 1 with draft_n 31 / accepted 31
    (100% acceptance) the output STILL differed from the no-MTP baseline. With every draft token
    accepted, "the drafts were bad" cannot explain it — enabling MTP perturbs the TARGET model's
    own forward pass. That is why Nova's grammar broke, words vanished and sentences truncated
    with MTP on, and why no sampler/prompt/LoRA change on our side can compensate.

    Both issues are CLOSED as "bug-unconfirmed" (no linked fix). So: retest, don't assume.

WHAT IT DOES
    Boots llama-server itself, once per configuration, with Nova's REAL launch args (dual-GPU
    split, -c 65536, her adapter at her scale), sends identical deterministic requests
    (temp 0, fixed seed, cache_prompt off), and diffs the committed TOKEN IDS — not the prose,
    the tokens. Byte-identical token streams = lossless = safe to enable. Any divergence = the
    bug is still present on this build; leave MTP off.

    Also reports tok/s per config, because MTP is not always faster: in #23335 it was SLOWER at
    every setting (10.2 baseline -> 8.8 at n=1 -> 4.3 at n=4).

WHEN TO RUN IT
    NOT routine. Only after a llama.cpp update, to check whether the upstream bug is fixed.
    Standing answer until then: keep MTP off.

BUDGET — READ THIS FIRST
    ~10-15 MINUTES with Nova fully DOWN the whole time. Four llama-server boots at ~40s each
    (26GB model) plus 16 generations. A short window is not enough — if you stop Nova and
    restart her a few minutes later, this will not have finished.

USAGE (from the workspace root)
    StopNova.cmd                                 # REQUIRED — it needs port 8080 to itself
    python _admin/mtp_ab_test.py                 # her adapter at her live scale
    python _admin/mtp_ab_test.py --no-lora       # isolate: is it MTP alone, or MTP+LoRA?
    python _admin/mtp_ab_test.py --n-max 1 2 3 4
    NovaStart.cmd                                # bring her back up when it's done

OUTPUT
    Printed to console AND written to _admin/mtp_ab_result_<timestamp>.{txt,json} so the
    verdict survives the terminal window closing.

EXIT CODE
    0 = every MTP config matched baseline exactly (safe to enable)
    1 = at least one diverged (keep MTP off)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WS         = Path(__file__).resolve().parent.parent
LLAMA_EXE  = WS / "llama" / "llama-server.exe"
MODEL      = WS / "models" / "qwen3.6" / "Qwen3.6-27B-UD-Q6_K_XL.gguf"
PORT       = 8080
BASE_URL   = f"http://127.0.0.1:{PORT}"

# Deterministic probes. Mixed on purpose: prose (grammar/dropped words), a long-form answer
# (truncation), and reasoning (the register she actually works in). n_predict is generous so a
# cut-off sentence shows up as a token-stream divergence rather than a length cap.
PROBES = [
    ("prose",     "Write four sentences about how local language models keep data private."),
    ("longform",  "Explain, in one paragraph, why a personality adapter can make a model loop."),
    ("reasoning", "A task takes 3 steps. Each step waits 90 seconds. How long total? Think it through."),
    ("voice",     "Someone just corrected you and they were right. Reply in two honest sentences."),
]
N_PREDICT = 160


def active_adapter() -> tuple[str, float] | None:
    """Whatever nova_start.py would boot: memory/active_lora.json, else the v2 default."""
    p = WS / "memory" / "active_lora.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("rel") and (WS / d["rel"]).exists():
                return str(d["rel"]), float(d.get("scale", 1.0))
        except Exception:
            pass
    fallback = "models/qwen3.6/nova_core_v2_e2.gguf"
    return (fallback, 0.6) if (WS / fallback).exists() else None


def build_cmd(spec_n_max: int | None, use_lora: bool) -> list[str]:
    """Nova's real launch args (nova_start.py), plus/minus the MTP flags."""
    cmd = [str(LLAMA_EXE), "-m", str(MODEL), "-ngl", "999",
           "-c", "65536", "--parallel", "1",
           "-b", "2048", "-ub", "1024",
           "--jinja", "--port", str(PORT), "--host", "127.0.0.1"]
    try:  # dual-GPU split, matching her launcher
        if subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True,
                          timeout=8).stdout.count("GPU ") >= 2:
            cmd += ["--tensor-split", "12,28"]
    except Exception:
        pass
    if use_lora:
        sel = active_adapter()
        if sel:
            cmd += ["--lora-scaled", f"{Path(sel[0]).as_posix()}:{sel[1]}"]
    if spec_n_max is not None:
        cmd += ["--spec-type", "draft-mtp",
                "--spec-draft-n-max", str(spec_n_max), "--spec-draft-n-min", "0"]
    return cmd


def wait_healthy(proc: subprocess.Popen, timeout: int = 420) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"    ! llama-server exited early (code {proc.returncode})")
            return False
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def run_probe(prompt: str) -> dict:
    """Fully deterministic single completion; returns committed token ids + timing."""
    body = json.dumps({
        "prompt": ("<|im_start|>system\nYou are concise and helpful.<|im_end|>\n"
                   f"<|im_start|>user\n{prompt}<|im_end|>\n"
                   "<|im_start|>assistant\n<think>\n\n</think>\n\n"),
        "n_predict": N_PREDICT,
        "temperature": 0, "top_k": 40, "top_p": 0.9, "min_p": 0,
        "seed": 1234, "cache_prompt": False, "stream": False, "return_tokens": True,
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode())
    t = d.get("timings", {})
    return {"tokens": d.get("tokens", []), "content": d.get("content", ""),
            "tok_s": round(t.get("predicted_per_second", 0), 2),
            "draft_n": t.get("draft_n"), "draft_accepted": t.get("draft_n_accepted")}


def run_config(label: str, spec_n_max: int | None, use_lora: bool) -> dict | None:
    print(f"\n=== {label} ===")
    cmd = build_cmd(spec_n_max, use_lora)
    print("    " + " ".join(cmd[1:]))
    proc = subprocess.Popen(cmd, cwd=str(WS),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_healthy(proc):
            print("    ! never became healthy — skipping")
            return None
        out = {}
        for name, prompt in PROBES:
            r = run_probe(prompt)
            out[name] = r
            extra = ""
            if r["draft_n"]:
                acc = 100.0 * (r["draft_accepted"] or 0) / r["draft_n"]
                extra = f"  draft {r['draft_accepted']}/{r['draft_n']} ({acc:.0f}% accepted)"
            print(f"    {name:<10} {len(r['tokens']):>4} tok  {r['tok_s']:>6} tok/s{extra}")
        return out
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(6)   # let the port and VRAM actually release


class Tee:
    """Everything printed also lands in a file — so the verdict survives the console closing.
    (2026-07-19: the first run of this script produced no reviewable output for exactly that
    reason, and there was no way to tell afterwards whether it had even run.)"""

    def __init__(self, path: Path):
        self.f = open(path, "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, s):
        self.stdout.write(s)
        self.f.write(s)
        self.f.flush()

    def flush(self):
        self.stdout.flush()
        self.f.flush()

    def close(self):
        self.f.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", nargs="*", type=int, default=[1, 2, 3])
    ap.add_argument("--no-lora", action="store_true")
    args = ap.parse_args()

    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    txt_path = WS / "_admin" / f"mtp_ab_result_{stamp}.txt"
    json_path = WS / "_admin" / f"mtp_ab_result_{stamp}.json"
    tee = Tee(txt_path)
    sys.stdout = tee
    try:
        return _run(args, json_path, txt_path)
    finally:
        sys.stdout = tee.stdout
        tee.close()
        print(f"\nSaved: {txt_path.name} / {json_path.name}  (in _admin/)")


def _run(args, json_path: Path, txt_path: Path) -> int:
    if not LLAMA_EXE.exists() or not MODEL.exists():
        print(f"missing binary or model:\n  {LLAMA_EXE}\n  {MODEL}")
        return 1
    try:
        urllib.request.urlopen(f"{BASE_URL}/health", timeout=2)
        print("=" * 68)
        print(f"  ABORTED — something is already serving :{PORT}.")
        print("  Run StopNova.cmd first, then re-run this. Nova must stay DOWN for")
        print("  the whole test (~10-15 min: 4 model loads + 16 generations).")
        print("=" * 68)
        return 1
    except Exception:
        pass
    print(f"[budget] ~10-15 minutes, Nova down throughout. Started {time.strftime('%H:%M:%S')}.")

    use_lora = not args.no_lora
    sel = active_adapter()
    print("MTP correctness A/B")
    print(f"  adapter: {sel[0]}:{sel[1]}" if (use_lora and sel) else "  adapter: NONE (bare base)")
    print(f"  probes : {len(PROBES)} x {N_PREDICT} tok, temp 0, seed 1234")
    print("  rule   : identical token ids vs baseline = lossless = safe to enable")

    baseline = run_config("BASELINE (MTP off)", None, use_lora)
    if not baseline:
        print("\nBaseline failed to run — cannot compare.")
        return 1

    results, all_ok = [], True
    for n in args.n_max:
        got = run_config(f"MTP draft-mtp, --spec-draft-n-max {n}", n, use_lora)
        if not got:
            all_ok = False
            results.append((n, None, []))
            continue
        diverged = [name for name, _ in PROBES
                    if got[name]["tokens"] != baseline[name]["tokens"]]
        results.append((n, got, diverged))
        if diverged:
            all_ok = False

    print("\n" + "=" * 68)
    print("VERDICT")
    print("=" * 68)
    base_speed = sum(baseline[n]["tok_s"] for n, _ in PROBES) / len(PROBES)
    print(f"  baseline (MTP off): {base_speed:.2f} tok/s avg")
    for n, got, diverged in results:
        if got is None:
            print(f"  n_max {n}: DID NOT RUN")
            continue
        speed = sum(got[name]["tok_s"] for name, _ in PROBES) / len(PROBES)
        delta = (speed / base_speed - 1) * 100 if base_speed else 0
        if diverged:
            print(f"  n_max {n}: ✗ DIVERGED on {', '.join(diverged)} "
                  f"— {speed:.2f} tok/s ({delta:+.0f}%) — DO NOT ENABLE")
            for name in diverged[:1]:
                b, g = baseline[name]["tokens"], got[name]["tokens"]
                i = next((k for k in range(min(len(b), len(g))) if b[k] != g[k]), None)
                if i is not None:
                    print(f"      first divergence at token {i}: "
                          f"baseline {b[i]} vs mtp {g[i]}")
                    print(f"      baseline: …{baseline[name]['content'][max(0,i*3-60):i*3+60]!r}")
                    print(f"      mtp     : …{got[name]['content'][max(0,i*3-60):i*3+60]!r}")
        else:
            print(f"  n_max {n}: ✓ identical to baseline "
                  f"— {speed:.2f} tok/s ({delta:+.0f}%) — safe")

    print()
    if all_ok:
        print("  ALL CONFIGS LOSSLESS on this build. Pick the fastest that is ✓ and")
        print("  re-enable the --spec-* lines in nova_start.py. Then run a real")
        print("  conversation before trusting it.")
    else:
        print("  The llama.cpp MTP bug (#23302 / #23335) is STILL PRESENT on this build.")
        print("  Keep MTP off in nova_start.py. Re-run this after the next llama.cpp update.")

    # Machine-readable record, so a later session can diff builds without re-running.
    try:
        json_path.write_text(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "adapter": (None if args.no_lora else active_adapter()),
            "baseline_tok_s": round(base_speed, 2),
            "all_lossless": all_ok,
            "configs": [
                {"n_max": n,
                 "ran": got is not None,
                 "diverged_probes": diverged,
                 "tok_s": (round(sum(got[nm]["tok_s"] for nm, _ in PROBES) / len(PROBES), 2)
                           if got else None)}
                for n, got, diverged in results
            ],
        }, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  (could not write json record: {e})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
