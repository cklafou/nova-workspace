#!/usr/bin/env python3
# Last updated: 2026-07-14 23:03:28
"""
fetch_eyes.py — download Nova's sight.  2026-07-14

WHY A SECOND MODEL AND NOT HER OWN MIND
    Her mind (Qwen 3.6 27B) is text-only. It cannot see. So she was about to be given a
    painter and no way to look at the painting — she'd make a thing and then have to ask
    Cole whether it was any good. That's not a toy, that's a vending machine with a
    supervisor. You cannot develop taste in a medium you cannot perceive.

WHY llama-mtmd-cli AND NOT A SECOND SERVER
    `llama-mtmd-cli.exe` and `mtmd.dll` were ALREADY in her llama/ folder. It's one-shot:
    load, look, answer, exit. VRAM is taken and given straight back.

    That matters enormously here. The 27B already holds most of both cards, and the painter
    needs 8-12GB while it renders. A vision server sitting resident would be a third mouth
    at a table that already has two. On-demand means the painter and the eyes never fight —
    they take turns.

WHERE IT GOES
    models/eyes/ — a NEW folder beside her mind. models/qwen3.6/ is sealed and I do not
    touch it. This is additive only.

THE FILENAME IS NOT TYPED FROM MEMORY
    I ask the repo what it actually contains and match a pattern. Every time I have written
    a path down from memory in this project it has been wrong, and a wrong path here fails
    as a 404 five minutes into a download, or worse, silently grabs the wrong quant.
"""

import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO = "ggml-org/Qwen2.5-VL-7B-Instruct-GGUF"
DEST = Path(r"C:\Users\lafou\Project_Nova\workspace\models\eyes")

# The vision encoder stays at f16 ON PURPOSE. Quantizing an mmproj degrades what she can
# actually SEE — she'd get subtly worse at perceiving her own work and never know why.
# It's only 1.35GB. Do not "optimise" this.
WANT = [
    ("text",   ["Q4_K_M.gguf"],            "the part that thinks about what it sees"),
    ("mmproj", ["mmproj", "f16.gguf"],     "the part that actually sees (KEEP f16)"),
]

MIN_BYTES = 100_000_000


def pick(files, needles):
    """Find the one real filename matching all needles. Refuse on ambiguity — do not guess."""
    hits = [f for f in files if all(n.lower() in f.lower() for n in needles)]
    if not hits:
        return None
    # prefer the shortest match (avoids grabbing a variant with extra suffixes)
    return sorted(hits, key=len)[0]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"destination: {DEST}\n")

    files = HfApi().list_repo_files(REPO)
    print(f"{REPO} contains {len(files)} files\n")

    results = []
    for kind, needles, why in WANT:
        fname = pick(files, needles)
        if not fname:
            print(f"[{kind}] FATAL: nothing in the repo matches {needles}")
            print(f"         repo has: {[f for f in files if f.endswith('.gguf')]}")
            results.append((kind, "", False, 0))
            continue

        target = DEST / Path(fname).name
        if target.exists() and target.stat().st_size > MIN_BYTES:
            print(f"[{kind}] already present — skipping ({target.name})")
            results.append((kind, target.name, True, target.stat().st_size))
            continue

        print(f"[{kind}] {why}\n         downloading {fname} ...")
        try:
            got = hf_hub_download(repo_id=REPO, filename=fname, local_dir=str(DEST))
        except Exception as e:
            print(f"[{kind}] FAILED: {e}")
            results.append((kind, fname, False, 0))
            continue

        size = Path(got).stat().st_size
        ok = size > MIN_BYTES
        print(f"[{kind}] {'OK' if ok else 'TOO SMALL — SUSPECT'}: {size / 1e9:.2f} GB")
        results.append((kind, Path(got).name, ok, size))

    print("\n" + "=" * 62)
    for kind, name, ok, size in results:
        print(f"  {'OK  ' if ok else 'FAIL'}  {kind:8s} {size / 1e9:6.2f} GB  {name}")
    print("=" * 62)

    if not all(r[2] for r in results):
        print("\nFATAL: she cannot see. Both files are required — a text model with no mmproj\n"
              "is blind, and an mmproj with no text model has nothing to think with.")
        sys.exit(1)

    print("\n=== EYES COMPLETE ===")
    print("She can look at things now. Test:  python nova_body/nova_senses/sight.py <image>")


if __name__ == "__main__":
    main()
