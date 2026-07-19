#!/usr/bin/env python3
# Last updated: 2026-07-19 14:05:08
"""
fetch_checkpoints.py — download Nova's paints.  2026-07-14

Three checkpoints, chosen for RANGE, not redundancy. Illustrious/Pony/Animagine are
all stylized-anime-character models; giving her all three would be three shades of one
lamp. So: two character models with different temperaments, and one that can render a
PLACE — because a palette that can only draw people quietly means "you may only draw
yourself."

  illustrious  clean stylized linework. Her cyber-elf look. The base we'll train her
               self-LoRA on later, so this one is load-bearing.
  pony         also stylized, but much better prompt adherence — she can ask for weirder,
               more specific things and actually get them. This is the PLAY one.
  realism      photoreal SDXL. Scenes, objects, places, moods. Not-a-character.

EVERY PATH HERE WAS VERIFIED against HuggingFace before being written down. I did not
type a repo id from memory. Guessing a URL is the same fabrication reflex we've spent
this whole project building structure against — and it would have failed silently as a
404 three minutes into a 21GB download.

NOTE ON PROVENANCE (say the true thing): Illustrious and RealVis are official author
repos. Pony's official home is Civitai, which needs a login — `LyliaEngine` is a
community re-upload. It's the standard route and the file is the canonical
`ponyDiffusionV6XL_v6StartWithThisOne.safetensors`, but it is a third-party mirror and
Cole should know that rather than have me quietly present it as first-party.

Verifies bytes landed. A download that reports success and writes nothing is the exact
bug class that has cost this project the most (see Orient/GOTCHAS.md).
"""

import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

DEST = Path(r"C:\Users\lafou\ComfyUI\models\checkpoints")

# (nickname, repo_id, filename, approx_GB)  — all three confirmed to exist, 2026-07-14
CHECKPOINTS = [
    ("illustrious", "OnomaAIResearch/Illustrious-XL-v2.0",
     "Illustrious-XL-v2.0.safetensors", 6.94),
    ("pony", "LyliaEngine/Pony_Diffusion_V6_XL",
     "ponyDiffusionV6XL_v6StartWithThisOne.safetensors", 6.94),
    ("realism", "SG161222/RealVisXL_V5.0",
     "RealVisXL_V5.0_fp16.safetensors", 6.94),
    # Flux is a DIFFERENT ARCHITECTURE, not another SDXL. It's the only one here that
    # understands complicated instructions, gets spatial composition right, and can put
    # readable TEXT in a picture. Posters, diagrams, jokes with words in them.
    # This is the all-in-one fp8 build: both text encoders and the VAE are baked in, so
    # CheckpointLoaderSimple can load it like any other checkpoint. 17.2GB — bigger than I
    # first told Cole (I said ~7). Saying so.
    ("flux", "Comfy-Org/flux1-dev",
     "flux1-dev-fp8.safetensors", 17.2),
]

MIN_BYTES = 1_000_000_000  # a real SDXL checkpoint is ~7GB. Anything under 1GB is an error page.


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"destination: {DEST}\n")

    results = []
    for nick, repo, fname, gb in CHECKPOINTS:
        target = DEST / fname
        if target.exists() and target.stat().st_size > MIN_BYTES:
            print(f"[{nick}] already present ({target.stat().st_size / 1e9:.2f} GB) — skipping")
            results.append((nick, fname, True, target.stat().st_size))
            continue

        print(f"[{nick}] downloading {repo}/{fname}  (~{gb} GB)...")
        try:
            got = hf_hub_download(
                repo_id=repo, filename=fname,
                local_dir=str(DEST),          # real file, not a symlink into the hub cache —
                                              # ComfyUI scans this dir and must SEE the file
            )
        except Exception as e:
            print(f"[{nick}] FAILED: {e}")
            results.append((nick, fname, False, 0))
            continue

        size = Path(got).stat().st_size
        ok = size > MIN_BYTES
        print(f"[{nick}] {'OK' if ok else 'TOO SMALL — SUSPECT'}: {size / 1e9:.2f} GB -> {got}")
        results.append((nick, fname, ok, size))

    # ── Verify. Do not report success for a thing you did not look at. ──
    print("\n" + "=" * 62)
    good = [r for r in results if r[2]]
    for nick, fname, ok, size in results:
        print(f"  {'OK  ' if ok else 'FAIL'}  {nick:12s} {size / 1e9:6.2f} GB  {fname}")
    print("=" * 62)
    print(f"{len(good)}/{len(CHECKPOINTS)} checkpoints on disk.")

    if not good:
        print("\nFATAL: no checkpoints landed. Nova cannot draw.")
        sys.exit(1)
    if len(good) < len(CHECKPOINTS):
        print("\nPARTIAL — she can draw, but her palette is short. See failures above.")
        sys.exit(2)

    print("\n=== CHECKPOINTS COMPLETE ===")
    print("NEXT: run C:\\Users\\lafou\\ComfyUI\\run_nova_painter.bat")


if __name__ == "__main__":
    main()
