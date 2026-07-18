#!/usr/bin/env python3
# Last updated: 2026-07-18 21:27:59
"""
downloads.py — how far along is everything, actually.

Cole asked "how can I see the progress of these?" and the honest answer was: you couldn't.
hf_hub_download draws its bar to stderr, which went into a log file, where a progress bar
is worse than useless — it's thousands of carriage-returns.

So measure the thing itself. HuggingFace streams into a `.incomplete` file and renames it
on success, so the partial file's size IS the progress. No guessing, no parsing a log, no
trusting anyone's account of it. Look at the bytes.

    python _admin/downloads.py           once
    python _admin/downloads.py --watch   live, refreshes every 3s
"""

import sys
import time
from pathlib import Path

CKPT = Path(r"C:\Users\lafou\ComfyUI\models\checkpoints")

# what we're expecting, and how big it should end up (bytes)
WANT = [
    ("illustrious", "Illustrious-XL-v2.0.safetensors", 6_940_000_000),
    ("pony", "ponyDiffusionV6XL_v6StartWithThisOne.safetensors", 6_940_000_000),
    ("real", "RealVisXL_V5.0_fp16.safetensors", 6_940_000_000),
    ("flux", "flux1-dev-fp8.safetensors", 17_200_000_000),
]


def live_partial():
    """The download actually in flight right now: (bytes, seconds_since_written).

    HF stashes in-flight downloads under .cache/huggingface/download/*.incomplete — but it
    names them by HASH, not by filename. My first version matched on the filename, found
    nothing, and cheerfully printed "not started" while 17GB was streaming past it.

    A progress bar that says 0% during a live download is worse than no progress bar: it's
    the same lie as a tool that reports success and does nothing, just pointed at Cole
    instead of at Nova. So don't match names. Look at which file is BEING WRITTEN.

    The fetcher downloads sequentially, so there is exactly one live .incomplete — the one
    touched in the last few seconds. Stale ones are corpses from runs I killed."""
    cache = CKPT / ".cache" / "huggingface" / "download"
    if not cache.is_dir():
        return 0, 1e9
    inc = [f for f in cache.rglob("*.incomplete") if f.is_file()]
    if not inc:
        return 0, 1e9
    newest = max(inc, key=lambda f: f.stat().st_mtime)
    return newest.stat().st_size, time.time() - newest.stat().st_mtime


def bar(frac: float, width: int = 28) -> str:
    frac = max(0.0, min(1.0, frac))
    n = int(frac * width)
    return "[" + "#" * n + "-" * (width - n) + "]"


def report() -> bool:
    """Returns True when everything is done.

    LIVENESS IS MEASURED, NOT INFERRED. My second attempt used the .incomplete file's
    mtime to decide whether a download was moving — and reported "STALLED, nothing written
    for 40s" over a download that was streaming at 11 MB/s. Windows does not reliably
    update the last-write timestamp on an OPEN file handle.

    So don't ask the clock. Ask the file how big it is, wait two seconds, and ask again.
    If it grew, it's alive, and the delta gives you the speed and the ETA for free.
    Two samples of the real thing beat one reading of a proxy."""
    all_done = True
    lines = []

    # Sample over 6s, not 2. HF writes in big chunks, so a 2-second window can legitimately
    # see zero growth mid-download — and my last version called that "STALLED" over a live
    # transfer. Third time I've mistaken a quiet moment for a dead one today. Widen the
    # window until the measurement is actually capable of seeing the thing it's measuring.
    a, _ = live_partial()
    time.sleep(6.0)
    b, _ = live_partial()
    speed = max(0, b - a) / 6.0          # bytes/sec, actually observed
    claimed = False

    for nick, fname, expect in WANT:
        done = CKPT / fname
        if done.is_file() and done.stat().st_size > 1_000_000_000:
            lines.append(f"  DONE     {nick:12s} {bar(1.0)} {done.stat().st_size/1e9:6.2f} GB")
            continue

        all_done = False
        if b and not claimed:
            claimed = True
            frac = b / expect
            if speed > 100_000:
                eta = (expect - b) / speed
                tail = f"{speed/1e6:5.1f} MB/s   {int(eta//60)}m{int(eta%60):02d}s left"
            else:
                tail = "STALLED — no bytes moving"
            lines.append(f"  {'...' if speed > 100_000 else 'STOP'}      {nick:12s} {bar(frac)} "
                         f"{b/1e9:5.2f}/{expect/1e9:.1f} GB ({frac*100:4.1f}%)  {tail}")
        else:
            lines.append(f"  waiting  {nick:12s} {bar(0)}   queued")

    print("\n".join(lines))
    return all_done


if __name__ == "__main__":
    watch = "--watch" in sys.argv
    while True:
        print(f"\nNova's paints — {time.strftime('%H:%M:%S')}")
        done = report()
        if done:
            print("\n  All four on disk.")
            break
        if not watch:
            break
        time.sleep(3)
