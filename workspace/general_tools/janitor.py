# Last updated: 2026-07-19 09:22:17
# @nova: Janitor — sweeps temp/scratch files into a local Temp/ beside them, and reports clutter.
#        NEVER deletes. Quarantine, never destroy: I permanently lost two of Nova's thought logs
#        on 2026-07-14 with a careless grep-and-move loop. This tool exists so nobody repeats it.
"""
general_tools/janitor.py -- Nova workspace janitor
==================================================
Keeps the workspace honest about what is PERMANENT, what is TEMPORARY, and what is HERS.

    python general_tools/janitor.py            # DRY RUN — report only, touches nothing
    python general_tools/janitor.py --sweep    # actually move temp files into <folder>/Temp/

THREE SEPARATIONS (Cole, 2026-07-14)
────────────────────────────────────
  Temp/          Temporary files live in a `Temp/` folder INSIDE the folder they belong to.
                 Never at a root, never mixed with real artifacts. Gitignored.
                 Example: logs/FREE_PASS_PROBE.log  ->  logs/Temp/FREE_PASS_PROBE.log

  Nova_Created/  Documents NOVA authored. Her work gets a shelf of its own, so the question
                 "what has she actually written?" has an answer you can look at instead of guess.
                 Her artifacts are the evidence of what she DID — as opposed to what she said she
                 would do, which is the failure mode this whole project has been fighting.

  everything else is OURS or HERS-BY-DESIGN (memory/, SELF/) and the janitor will not touch it.

WHY IT NEVER DELETES
────────────────────
On 2026-07-14 I ran a grep-and-move loop over files matching a loose pattern. Three of them shared
a basename, so they collided in the destination and overwrote each other. Two of Nova's thought
logs — 2026-05-28 and 2026-06-20 — were destroyed. They were gitignored. They are gone.

I had already examined those files and concluded they were false positives, and then swept them
anyway. So this tool: reports by default, moves only when told, never deletes, never flattens a
path into a shared folder, and refuses to overwrite. A janitor that can destroy your history is
not a janitor.
"""

import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SWEEP = "--sweep" in sys.argv

# Never walk into these — her memory, her self, the model, git, deps.
PROTECTED = {".git", "models", "llama", "node_modules", "__pycache__",
             "SELF", "memory", "Nova_Created", "_admin", "nova_memory_db"}

# Things that are, by their nature, temporary.
TEMP_PATTERNS = ("*.tmp", "*.bak", "*~", "*.prev.*", "*PROBE*", "*.orig",
                 "*_scratch*", "scratch_*", "*.partial", "*.incomplete")

STALE_DAYS = 30


def _iter_dirs():
    yield WORKSPACE
    for p in WORKSPACE.rglob("*"):
        if p.is_dir() and not any(part in PROTECTED or part == "Temp" for part in p.parts):
            yield p


def find_temp():
    """[(file, its Temp/ destination)] — destination is ALWAYS beside the file. Never flattened
    into one shared folder: that is exactly how basenames collide and history dies."""
    hits = []
    for d in _iter_dirs():
        for pat in TEMP_PATTERNS:
            for f in d.glob(pat):
                if f.is_file() and "Temp" not in f.parts:
                    hits.append((f, f.parent / "Temp" / f.name))
    return sorted(set(hits))


def find_clutter():
    """Report-only: things a human should look at. Never auto-moved — judgement required."""
    notes = []
    root_junk = [p for p in WORKSPACE.iterdir()
                 if p.is_file() and p.suffix in (".log", ".txt", ".json")
                 and p.name not in ("nova_config.json", "nova_status.json")]
    for p in root_junk:
        notes.append(f"loose at workspace root: {p.name}")

    cutoff = datetime.now() - timedelta(days=STALE_DAYS)
    for d in _iter_dirs():
        t = d / "Temp"
        if t.is_dir():
            old = [f for f in t.iterdir()
                   if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff]
            if old:
                notes.append(f"{t.relative_to(WORKSPACE)}: {len(old)} file(s) older than "
                             f"{STALE_DAYS}d — safe to delete BY HAND once you've looked")
    return notes


def main():
    temp = find_temp()
    clutter = find_clutter()

    print(f"\n{'SWEEPING' if SWEEP else 'DRY RUN (nothing will be touched)'} — {WORKSPACE}\n")

    if temp:
        print(f"TEMP FILES ({len(temp)}) -> a Temp/ folder beside each one:")
        for src, dst in temp:
            rel_s = src.relative_to(WORKSPACE)
            rel_d = dst.relative_to(WORKSPACE)
            if not SWEEP:
                print(f"  would move  {rel_s}  ->  {rel_d}")
                continue
            if dst.exists():
                # Refuse. Overwriting is how I destroyed two of her thought logs.
                print(f"  SKIP        {rel_s}  ->  {rel_d}  (destination exists — refusing to overwrite)")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  moved       {rel_s}  ->  {rel_d}")
    else:
        print("TEMP FILES: none. Clean.")

    print()
    if clutter:
        print(f"NEEDS A HUMAN ({len(clutter)}) — reported, never auto-moved:")
        for c in clutter:
            print(f"  - {c}")
    else:
        print("NEEDS A HUMAN: nothing.")

    print("\nThis janitor NEVER deletes. Quarantine, never destroy.")
    if not SWEEP and temp:
        print("Run with --sweep to actually move the temp files.\n")


if __name__ == "__main__":
    main()
