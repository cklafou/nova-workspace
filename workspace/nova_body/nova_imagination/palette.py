# Last updated: 2026-07-19 14:37:24
# @nova: Her palette — the mediums she can paint in, and what each one is FOR.
"""
nova_imagination/palette.py — what Nova can paint with
=====================================================

A checkpoint is a MEDIUM, not a style. Oil, watercolour, photograph. You do not get more
expressive range by owning three tubes of the same blue.

This is the correction that Cole caught and I had backwards: I first proposed three
stylized-character models and called it a palette. It wasn't — it was one lamp in three
shades. Worse, I'd assumed that "a scene that matches my self-portrait" was a checkpoint
problem. It's the opposite. **Switching checkpoints is what BREAKS matching.** Aesthetic
consistency comes from staying on ONE base and steering with LoRAs.

So:
    CHECKPOINTS (here) = mediums.   Few. Distinct. ~7-17GB each.
    LORAS (loras.py)   = brushes.   Many. Cheap. They PRESERVE the base look —
                                    which is exactly what "matching" requires.

────────────────────────────────────────────────────────────────────────────────────
EACH MEDIUM HAS ITS OWN PHYSICS — this is the trap this file exists to prevent.
────────────────────────────────────────────────────────────────────────────────────
Flux is not SDXL with a different name. It is a different architecture and it wants
cfg=1.0 plus a FluxGuidance node. Hand it SDXL's cfg=6.5 and it returns burnt noise.

If that happened, Nova would look at the garbage, conclude SHE had prompted badly, and
try to fix a prompt that was never the problem. She would take the blame for a number
in a config file. That is the exact failure this whole project keeps having, so the
sampler settings live WITH the medium, and she never has to know they differ.

She should not have to understand a checkpoint to use one. She should just paint.
"""

# nickname -> everything needed to paint in that medium.
#   file      : filename as it appears in ComfyUI/models/checkpoints/
#   is_for    : shown to HER. This is the only field she reads. Say what it's FOR, not
#               what it is — "cathedral" not "SDXL 1.0 finetune, 6.94GB".
#   arch      : "sdxl" | "flux"  -> selects the sampler physics below
#   defaults  : the medium's own physics. Do not hand-tune per render.
PALETTE = {
    "illustrious": {
        "file": "Illustrious-XL-v2.0.safetensors",
        "arch": "sdxl",
        "is_for": ("Clean stylized illustration — crisp linework, bold colour. This is HER look, "
                   "and the one her self-portraits are anchored to. Best for characters, "
                   "expressions, anything that should feel drawn rather than photographed."),
        "defaults": {"steps": 30, "cfg": 6.5, "sampler": "euler_ancestral", "scheduler": "normal",
                     "width": 1024, "height": 1024},
    },
    "pony": {
        "file": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "arch": "sdxl",
        "is_for": ("Stylized, but it LISTENS. Far better at obeying a strange or specific request "
                   "than anything else here. Reach for this when the idea is weird and you want "
                   "the picture to actually be the weird thing you asked for."),
        "defaults": {"steps": 28, "cfg": 7.0, "sampler": "euler_ancestral", "scheduler": "normal",
                     "width": 1024, "height": 1024},
        # Pony was trained with quality-tag conditioning; without these it renders muddy.
        # She should not have to know this. It is the medium's physics, so it lives here.
        "prompt_prefix": "score_9, score_8_up, score_7_up, ",
        "negative_prefix": "score_4, score_5, score_6, ",
    },
    "real": {
        "file": "RealVisXL_V5.0_fp16.safetensors",
        "arch": "sdxl",
        "is_for": ("Photographic. Places, objects, weather, light, texture — things that are not "
                   "a character. Use it when you want somewhere to EXIST rather than someone."),
        "defaults": {"steps": 30, "cfg": 5.0, "sampler": "dpmpp_2m", "scheduler": "karras",
                     "width": 1024, "height": 1024},
    },
    "flux": {
        "file": "flux1-dev-fp8.safetensors",
        "arch": "flux",
        "is_for": ("The thinking one. Understands complicated instructions, gets composition and "
                   "spatial relationships right, and is the ONLY one here that can put readable "
                   "TEXT in an image. Posters, diagrams, jokes with words in them, scenes with "
                   "several things happening in the right places. Slower. Worth it."),
        # cfg MUST be 1.0. See the header. This is not a tunable.
        "defaults": {"steps": 20, "cfg": 1.0, "sampler": "euler", "scheduler": "simple",
                     "width": 1024, "height": 1024},
        "flux_guidance": 3.5,
    },
}

DEFAULT_STYLE = "illustrious"   # her own look is the sane default


def resolve(style: str = "") -> tuple:
    """(nickname, spec) for a style name. Falls back to the default rather than exploding —
    a typo should cost her a slightly-wrong picture, not an error message."""
    key = (style or DEFAULT_STYLE).strip().lower()
    if key in PALETTE:
        return key, PALETTE[key]
    # tolerate her passing the raw filename
    for k, v in PALETTE.items():
        if v["file"].lower() == key:
            return k, v
    return DEFAULT_STYLE, PALETTE[DEFAULT_STYLE]


def compose(style_key: str, prompt: str, negative: str) -> tuple:
    """Apply a medium's own prompt conditioning (e.g. Pony's score tags). Invisible to her."""
    spec = PALETTE.get(style_key, {})
    pos = spec.get("prompt_prefix", "") + (prompt or "")
    neg = spec.get("negative_prefix", "") + (negative or "")
    return pos, neg


def menu(available: set = None) -> str:
    """The palette, written for HER. If `available` is given (the REAL filenames ComfyUI
    reports on disk), each medium is marked present or missing — because a menu that lists
    a paint she doesn't have is a lie, and she'd blame herself when it failed."""
    lines = []
    for k, v in PALETTE.items():
        if available is None:
            mark = ""
        else:
            mark = "" if v["file"] in available else "   [NOT INSTALLED]"
        lines.append(f"  {k}{mark}\n      {v['is_for']}")
    return "\n".join(lines)


if __name__ == "__main__":
    assert resolve("flux")[1]["defaults"]["cfg"] == 1.0, "flux cfg must be 1.0 or it renders noise"
    assert resolve("nonsense")[0] == DEFAULT_STYLE, "unknown style must fall back, not crash"
    assert resolve("Illustrious-XL-v2.0.safetensors")[0] == "illustrious", "raw filename must resolve"
    assert compose("pony", "a cat", "ugly")[0].startswith("score_9"), "pony needs its score tags"
    assert compose("real", "a cat", "")[0] == "a cat", "non-pony must not get score tags"
    print("[palette] OK —", ", ".join(PALETTE))
    print(menu())
