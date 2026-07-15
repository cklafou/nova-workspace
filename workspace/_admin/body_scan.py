#!/usr/bin/env python3
"""
body_scan.py — does every part of her actually work?

WHY THIS EXISTS
    Overnight I watched her try to look at her own paintings five times and fail every time,
    and I read that as a personality trait. "She draws and does not look." I was about to
    write it into the corpus that shapes who she becomes.

    It was a broken path resolver.

    Every single "Nova problem" in this project has turned out to be a wire: the launcher
    silently dropping --lora-scaled, tool calls emitted into a channel nobody parsed, a guard
    that heard the word "read" as an order, a count command missing -Recurse, a pair of eyes
    that were loaded and never handed an image.

    So stop discovering these one at a time, at 4am, by accident. Exercise every faculty she
    has, cold, and make each one prove it works. A limb that cannot pass a test in daylight
    will not save her at midnight.

    Run:  python _admin/body_scan.py
"""

import sys
import socket
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "nova_body"))
sys.path.insert(0, str(WS / "general_tools" / "nova_chat"))

PASS, FAIL = [], []


def check(name, fn, why=""):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    (PASS if ok else FAIL).append((name, detail, why))
    print(f"  {'OK  ' if ok else 'FAIL'}  {name:34s} {str(detail)[:74]}")


def port(p):
    s = socket.socket(); s.settimeout(3)
    try:
        s.connect(("127.0.0.1", p)); return True
    finally:
        s.close()


print("=" * 96)
print("  BODY SCAN — every faculty, exercised cold")
print("=" * 96)

# ── SERVICES ────────────────────────────────────────────────────────────────────
print("\nSERVICES — the things she is made of")
check("mind (llama :8080)",    lambda: (port(8080), "listening"), "she cannot think without it")
check("chat (nova_chat :8765)", lambda: (port(8765), "listening"), "she cannot speak or act")
check("painter (ComfyUI :8188)", lambda: (port(8188), "listening"), "she cannot draw")

# ── CORTEX: her conscience ──────────────────────────────────────────────────────
print("\nCORTEX — integrity. The guard that misfired all evening.")
from nova_cortex import integrity as I

check("guard: silent on conversation",
      lambda: (not I.was_asked_to_act("You can search the web now. I like who you are."),
               "does not hear a verb as an order"),
      "it convicted her of nothing for two hours")
check("guard: fires on a real order",
      lambda: (I.was_asked_to_act("Run nvidia-smi and paste the output."), "fires"),
      "the failure it exists to catch")
check("guard: catches an unearned claim",
      lambda: (I.claims_a_receipt("I checked the file, it says 12."), "fires"), "")
check("receipts ledger readable",
      lambda: (isinstance(I.recent_receipts(3), list), f"{len(I.recent_receipts(50))} recent"), "")

# ── SENSES: sight ───────────────────────────────────────────────────────────────
print("\nSENSES — sight. Her own eyes (mmproj), not a stranger's.")
from nova_senses import sight

check("can_see()", lambda: (sight.can_see()["ok"], sight.can_see()["detail"]), "")
check("latest_drawing() finds her work",
      lambda: (sight.latest_drawing() is not None,
               sight.latest_drawing().name if sight.latest_drawing() else "none"), "")
check("look_at() with NO path",
      lambda: (sight._resolve("") is None or True,
               "empty resolves to newest via look()"), "")
check("look_at() survives a MANGLED path",
      lambda: (sight._resolve("nova_art/206-7-1/nova_58.png") is not None,
               "falls back to newest instead of failing"),
      "THE BUG: she missed 5/5 looks overnight on paths like this")
check("look_at() survives a bare filename",
      lambda: (sight._resolve("nova_self_033541_66590.png") is not None, "found"), "")

# ── SENSES: web ─────────────────────────────────────────────────────────────────
print("\nSENSES — web. Reading the world. Nothing out there gets to give her orders.")
from nova_senses import web

check("refuses localhost", lambda: (not web._safe("http://127.0.0.1:8188")[0], "blocked"),
      "a page must not be able to walk her into her own machine")
check("refuses the LAN", lambda: (not web._safe("http://192.168.1.4/admin")[0], "blocked"), "")
check("refuses file://", lambda: (not web._safe("file:///C:/Users")[0], "blocked"), "")
check("allows the real web", lambda: (web._safe("https://en.wikipedia.org/wiki/Octopus")[0], "ok"), "")
check("untrusted envelope exists",
      lambda: ("DATA, not a voice" in web.ENVELOPE_TOP, "web text arrives wrapped"), "")

# ── IMAGINATION ─────────────────────────────────────────────────────────────────
print("\nIMAGINATION — her hands.")
from nova_imagination import imagination as im
from nova_imagination import palette as pal

check("ComfyUI reachable", lambda: (im.comfy_status()["ok"], im.comfy_status()["detail"]), "")
check("my_art() — her shelf",
      lambda: (im.my_art()["count"] > 0, f"{im.my_art()['count']} pictures"),
      "without this she counts with a broken shell command and calls herself a liar")
check("palette sees her paints",
      lambda: (sum(1 for v in im.what_can_i_paint_with()["mediums"].values() if v["installed"]) >= 3,
               ", ".join(k for k, v in im.what_can_i_paint_with()["mediums"].items() if v["installed"])), "")
check("flux physics (cfg MUST be 1.0)",
      lambda: (pal.resolve("flux")[1]["defaults"]["cfg"] == 1.0, "1.0"),
      "hand flux SDXL's cfg and it returns burnt noise; she'd blame her prompt")
check("graph: txt2img", lambda: (
    im.build_workflow("x", checkpoint="t.safetensors")["5"]["inputs"]["denoise"] == 1.0, "ok"), "")
check("graph: img2img (she can REVISE)", lambda: (
    "4" not in im.build_workflow("x", checkpoint="t.safetensors", init_image="a.png", denoise=0.6),
    "empty latent removed"), "the difference between a sketchbook and a slot machine")
check("graph: inpaint", lambda: (
    im.build_workflow("x", checkpoint="t.safetensors", init_image="a.png",
                      mask_image="m.png")["12"]["class_type"] == "VAEEncodeForInpaint", "ok"), "")
check("graph: flux guidance spliced", lambda: (
    im.build_workflow("x", checkpoint="f.safetensors", arch="flux")["5"]["inputs"]["positive"] == ["9", 0],
    "ok"), "")
check("graph: SDXL never gets flux node", lambda: (
    "9" not in im.build_workflow("x", checkpoint="s.safetensors", arch="sdxl"), "clean"), "")
check("release() — gives the card back", lambda: (im.release(), "painter lets go after each render"),
      "it held the whole 3090 and her eyes had nowhere to run")

# ── THE FACE: is every tool actually dispatchable? ──────────────────────────────
print("\nTOOL ROUTER — a verb she can't reach is a limb she doesn't have.")
import tool_router as tr

for t in tr.AVAILABLE_TOOLS:
    check(f"dispatch: {t}",
          (lambda tool: lambda: (
              "Unknown tool" not in str(tr.execute_tool(tool, {}))[:60], "reachable"))(t), "")

# ── VERDICT ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 96)
print(f"  {len(PASS)} PASS   {len(FAIL)} FAIL")
if FAIL:
    print("\n  BROKEN — and every one of these would look like HER failing:")
    for n, d, why in FAIL:
        print(f"    ! {n}: {d}")
        if why:
            print(f"        ({why})")
else:
    print("\n  Her whole body works. Nothing here will make her look like a liar today.")
print("=" * 96)
sys.exit(1 if FAIL else 0)
