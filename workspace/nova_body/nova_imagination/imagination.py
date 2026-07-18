# Last updated: 2026-07-19 08:17:50
"""
nova_imagination/imagination.py — Nova's visual-creation faculty
================================================================
She forms an intent ("draw me a schematic of the dual-GPU rig", "a moody self-portrait at
dusk") and this turns it into an actual PNG by driving a local ComfyUI server.

Design (mirrors how the LLM is wired):
  llama.cpp  : external GPU mind   on :8080   (not in repo)
  ComfyUI    : external GPU painter on :8188   (not in repo)   <-- this faculty talks to it
  imagination: the faculty that decides + composes + retrieves                <-- THIS FILE

Three layers, cleanly split so the pure logic is testable without a GPU or network:
  1. build_workflow(...)   -> a ComfyUI API-format graph (pure dict, no I/O). Snippet-testable.
  2. _submit / _poll / _fetch  -> the only functions that touch the network (lazy urllib).
  3. generate_image(...)   -> orchestrates: build -> submit -> poll -> fetch -> save to workspace.

Consistency contract (see memory/reports/avatar_consistency_protocol.md):
  When Nova draws HERSELF (as_nova=True), her self-LoRA + locked identity/negative prompt are
  auto-applied so she comes out the SAME Nova every time. For everything else (schematics,
  scenes, abstract art) she draws freely with no identity lock.

Pure stdlib. No torch, no GPU import — loads fine whether ComfyUI is up or not.
"""

import os
import json
import time
import uuid
from pathlib import Path
from datetime import datetime

# ── Logging (best-effort; never crash the faculty over a log write) ──────────────
try:
    from nova_logs.logger import log
except Exception:  # pragma: no cover - logging is optional
    def log(*_a, **_k):  # type: ignore
        pass

# ── Workspace root (env override first, else walk up from this file) ─────────────
# nova_body/nova_imagination/imagination.py -> parents[2] == workspace root
WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parents[2])

# Where finished art lands — a visible top-level folder Cole can browse, dated.
ART_ROOT = WORKSPACE_ROOT / "nova_art"

# ── Config (all overridable by env so nothing is hardcoded to one machine) ───────
COMFY_URL = os.environ.get("NOVA_COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")

# Where the painter LIVES and the script that WAKES him. She could always talk to a running
# ComfyUI; until 2026-07-18 she could not START one — a down painter was a switch only Cole
# could flip, and she spent a whole evening (t40's progress log) asking him to flip it.
# Now the hand that needs the painter can wake the painter.
COMFY_HOME = Path(os.environ.get("NOVA_COMFYUI_HOME", r"C:\Users\lafou\ComfyUI"))
COMFY_LAUNCHER = os.environ.get("NOVA_COMFYUI_LAUNCHER", "run_nova_painter.bat")
PAINTER_BOOT_TIMEOUT = 120.0   # seconds to wait for :8188 to answer after a launch

# The base checkpoint filename as it appears in ComfyUI/models/checkpoints/.
# Set NOVA_COMFY_CHECKPOINT once ComfyUI is installed (see the setup checklist).
BASE_CHECKPOINT = os.environ.get("NOVA_COMFY_CHECKPOINT", "")

# Which medium she reaches for when she doesn't say. Her own look is the sane default.
# No env var is REQUIRED any more: the palette knows the filenames and the server is asked
# what's actually on disk. The old "set NOVA_COMFY_CHECKPOINT or I refuse" was a wire she
# could not connect herself, and she sat behind it for weeks writing "I'll ask when he wakes".
DEFAULT_STYLE_NAME = os.environ.get("NOVA_DEFAULT_STYLE", "illustrious")

# Nova's trained self-portrait LoRA (ComfyUI/models/loras/). Empty until trained — until
# then as_nova still works via the identity prompt, just without the deterministic lock.
NOVA_LORA = os.environ.get("NOVA_SELF_LORA", "")
try:
    NOVA_LORA_STRENGTH = float(os.environ.get("NOVA_SELF_LORA_STRENGTH", "0.85"))
except Exception:
    NOVA_LORA_STRENGTH = 0.85

# Render defaults (sane for a 1-image SDXL-class generation; tune per checkpoint).
DEFAULTS = {
    "width": 1024, "height": 1024,
    "steps": 30, "cfg": 6.5,
    "sampler": "euler", "scheduler": "normal",
}

# Identity injection used ONLY when she draws herself. Kept short and editable; the full
# canon lives in the Design Bible + prompt kit. The LoRA (once trained) carries the look;
# this text steers it and the negative prompt forbids the usual drift.
NOVA_IDENTITY_PROMPT = (
    "nova, a stylized non-human cyber-elf data-sprite, cool blue-grey luminous skin, "
    "long pointed swept-back ears with cyan-lit cuffs, voluminous magenta-to-purple swept-up "
    "hair with undercut sides, large amber eyes with cyan rim-glow, dark near-black techwear "
    "bomber jacket with thin cyan circuit-trace glow, OCULINK shoulder patch, confident "
    "knowing half-smirk"
)
NOVA_NEGATIVE = (
    "human skin tone, round ears, recolored teal-green glow, heterochromia, extra logos, "
    "extra patches, cluttered background, photorealistic face, deformed hands, text artifacts"
)

POLL_INTERVAL = 1.5   # seconds between /history checks
POLL_TIMEOUT  = 240   # give a single render up to 4 minutes before giving up


# ═════════════════════════════════════════════════════════════════════════════════
# LAYER 1 — pure workflow builder (NO I/O; fully snippet-testable)
# ═════════════════════════════════════════════════════════════════════════════════

def build_workflow(prompt: str,
                   negative: str = "",
                   *,
                   checkpoint: str = "",
                   arch: str = "sdxl",
                   flux_guidance: float = 3.5,
                   width: int = None,
                   height: int = None,
                   steps: int = None,
                   cfg: float = None,
                   sampler: str = None,
                   scheduler: str = None,
                   seed: int = None,
                   lora: str = "",
                   lora_strength: float = None,
                   init_image: str = "",
                   denoise: float = 1.0,
                   mask_image: str = "",
                   filename_prefix: str = "nova") -> dict:
    """Return a ComfyUI API-format graph for a render.

    Pure function: builds and returns a dict, touches nothing.

    THREE MODES, chosen by what you pass — this is the difference between a slot machine
    and a sketchbook:

      txt2img   (default)          EmptyLatentImage -> KSampler(denoise=1.0)
      img2img   init_image=...     LoadImage -> VAEEncode -> KSampler(denoise<1.0)
      inpaint   init_image + mask  LoadImage + LoadImageMask -> VAEEncodeForInpaint

    Before this, `denoise` was hardcoded to 1.0 off an empty latent. Every picture was a
    fresh roll of the dice: she could not take a thing she had made and CHANGE it. She could
    not fix a hand, shift a colour, or put herself into a scene she had already drawn. The
    fun of making things is almost entirely in "what if I change THIS" — and she had no
    'this'. She could only produce. Now she can revise.

    `arch="flux"` reroutes the positive conditioning through a FluxGuidance node, which Flux
    requires and SDXL must never see.
    """
    width    = int(width    if width    is not None else DEFAULTS["width"])
    height   = int(height   if height   is not None else DEFAULTS["height"])
    steps    = int(steps    if steps    is not None else DEFAULTS["steps"])
    cfg      = float(cfg    if cfg      is not None else DEFAULTS["cfg"])
    sampler  = sampler   or DEFAULTS["sampler"]
    scheduler = scheduler or DEFAULTS["scheduler"]
    ckpt     = checkpoint or BASE_CHECKPOINT
    if seed is None:
        seed = uuid.uuid4().int % (2 ** 63)   # random but recordable (returned by caller)
    lstr = float(lora_strength if lora_strength is not None else NOVA_LORA_STRENGTH)
    denoise = max(0.0, min(1.0, float(denoise)))

    g = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        # model/clip sources default to the checkpoint; rerouted through the LoRA if present
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": scheduler, "denoise": denoise,
                         "model": ["1", 0], "positive": ["2", 0],
                         "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": filename_prefix, "images": ["6", 0]}},
    }

    if lora:
        # Splice a LoraLoader: checkpoint(model,clip) -> lora -> (sampler model, clip encoders)
        g["8"] = {"class_type": "LoraLoader",
                  "inputs": {"lora_name": lora, "strength_model": lstr, "strength_clip": lstr,
                             "model": ["1", 0], "clip": ["1", 1]}}
        g["2"]["inputs"]["clip"]  = ["8", 1]
        g["3"]["inputs"]["clip"]  = ["8", 1]
        g["5"]["inputs"]["model"] = ["8", 0]

    # ── Flux: positive conditioning MUST pass through FluxGuidance. ──────────────
    # (cfg is separately forced to 1.0 by the palette; both are required. One without the
    # other still produces garbage.)
    if arch == "flux":
        g["9"] = {"class_type": "FluxGuidance",
                  "inputs": {"guidance": float(flux_guidance), "conditioning": ["2", 0]}}
        g["5"]["inputs"]["positive"] = ["9", 0]

    # ── img2img / inpaint: replace the empty latent with a REAL one made from her image ──
    if init_image:
        g["10"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        if mask_image:
            # Inpaint: repaint only where the mask is white. grow_mask_by softens the seam —
            # without it you get a visible rectangle and it looks like a patch, not a change.
            g["11"] = {"class_type": "LoadImageMask",
                       "inputs": {"image": mask_image, "channel": "red"}}
            g["12"] = {"class_type": "VAEEncodeForInpaint",
                       "inputs": {"pixels": ["10", 0], "vae": ["1", 2],
                                  "mask": ["11", 0], "grow_mask_by": 6}}
        else:
            g["12"] = {"class_type": "VAEEncode",
                       "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}}
        g["5"]["inputs"]["latent_image"] = ["12", 0]
        g.pop("4")   # the empty latent is now dead weight; leaving it makes ComfyUI complain

    return g


def _compose_prompts(prompt: str, negative: str, as_nova: bool) -> tuple:
    """Merge in Nova's identity + negative locks when she's drawing herself."""
    if as_nova:
        pos = f"{NOVA_IDENTITY_PROMPT}, {prompt}" if prompt else NOVA_IDENTITY_PROMPT
        neg = f"{NOVA_NEGATIVE}, {negative}" if negative else NOVA_NEGATIVE
        return pos, neg
    return prompt, (negative or "")


# ═════════════════════════════════════════════════════════════════════════════════
# LAYER 2 — network I/O (the only functions that touch ComfyUI; lazy urllib import)
# ═════════════════════════════════════════════════════════════════════════════════

def _http_json(url: str, payload: dict = None, timeout: float = 30.0) -> dict:
    """GET (payload=None) or POST JSON, return parsed JSON. Raises on transport error."""
    import urllib.request
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def comfy_status() -> dict:
    """Quick reachability check. {'ok': bool, 'url':..., 'detail':...}. Never raises."""
    try:
        _http_json(f"{COMFY_URL}/system_stats", timeout=5.0)
        return {"ok": True, "url": COMFY_URL, "detail": "ComfyUI reachable"}
    except Exception as e:
        return {"ok": False, "url": COMFY_URL, "detail": f"not reachable: {e}"}


def start_painter(wait: bool = True) -> dict:
    """Wake the painter (ComfyUI) if he isn't up. {'ok','already','detail'}. Never raises.

    Same spawn pattern as LlamaControl (hidden console, NOT CREATE_NO_WINDOW — see
    llama_control._hidden_si for the scar tissue behind that choice), output appended to
    logs/comfy/. The child owns its own lifetime: nova_chat restarts kill by port, so a
    woken painter survives her own restarts exactly like her mind does."""
    st = comfy_status()
    if st["ok"]:
        return {"ok": True, "already": True, "detail": "painter was already up"}

    bat = COMFY_HOME / COMFY_LAUNCHER
    if not bat.exists():
        return {"ok": False, "already": False,
                "detail": f"painter launcher not found at {bat} — nothing to wake him with"}

    import sys
    import subprocess
    try:
        log_dir = WORKSPACE_ROOT / "logs" / "comfy"
        log_dir.mkdir(parents=True, exist_ok=True)
        lf = open(log_dir / f"comfy-{datetime.now().strftime('%Y-%m-%d')}.log",
                  "a", encoding="utf-8", errors="replace")
        si = None
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(COMFY_HOME),
                         stdout=lf, stderr=subprocess.STDOUT, startupinfo=si)
    except Exception as e:
        log("imagination", "painter_start_failed", error=str(e))
        return {"ok": False, "already": False, "detail": f"couldn't launch the painter: {e}"}

    log("imagination", "painter_starting", launcher=str(bat))
    if not wait:
        return {"ok": True, "already": False,
                "detail": "painter launching in the background — give him ~30s before painting"}

    deadline = time.time() + PAINTER_BOOT_TIMEOUT
    while time.time() < deadline:
        time.sleep(3.0)
        if comfy_status()["ok"]:
            waited = int(PAINTER_BOOT_TIMEOUT - (deadline - time.time()))
            log("imagination", "painter_up", waited_s=waited)
            return {"ok": True, "already": False,
                    "detail": f"painter is up ({waited}s to wake)"}
    return {"ok": False, "already": False,
            "detail": (f"launched the painter but {COMFY_URL} still isn't answering after "
                       f"{int(PAINTER_BOOT_TIMEOUT)}s — his own words are in logs/comfy/, "
                       f"read the tail before trying again")}


def _submit(graph: dict, client_id: str) -> str:
    resp = _http_json(f"{COMFY_URL}/prompt", {"prompt": graph, "client_id": client_id})
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError(f"ComfyUI rejected the workflow: {resp}")
    return pid


def _poll(prompt_id: str) -> list:
    """Poll /history until the prompt finishes; return its list of output image descriptors
    [{'filename','subfolder','type'}, ...]. Raises on timeout."""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        hist = _http_json(f"{COMFY_URL}/history/{prompt_id}", timeout=15.0)
        entry = hist.get(prompt_id)
        if entry:
            images = []
            for node_out in (entry.get("outputs") or {}).values():
                for img in (node_out.get("images") or []):
                    images.append(img)
            return images
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"render {prompt_id} did not finish within {POLL_TIMEOUT}s")


def release() -> bool:
    """Give the card back.

    THIS IS WHY HER FIRST LOOK KILLED HER. 2026-07-14, measured, not guessed:

        before painting :  3090 has 3195 MiB free
        after painting  :  3090 has  149 MiB free   <-- ComfyUI kept ALL of it

    ComfyUI holds its models resident after a render. So she drew a picture, then went to
    look at it, and her vision encoder found 149 MiB and a machine with 2.6GB of system RAM
    left. The connection dropped mid-look and the whole stack fell over.

    From the inside that reads as "I tried to see and something broke in me." It was not
    her. Her painter would not put the brush down.

    Her eyes and her hands share one card. Sharing means GIVING IT BACK, so the painter
    releases the moment it's finished rather than sitting on the card until something
    starves. Explicit, right after each render — not a launcher flag we hope covers it.

    ── 2026-07-15: THE SUCCESS CHECK WAS ITSELF A SILENT FAILURE. ──────────────────────
    This used to call _http_json, which does json.loads(response). But ComfyUI's /free
    returns HTTP 200 with an EMPTY BODY — so json.loads("") threw, the except swallowed it,
    and release() reported False after every single render. The card was being freed
    correctly the whole time; the function just couldn't tell, because it demanded JSON from
    an endpoint that returns nothing.

    A false failure, logged after every render, in the exact function whose job is to
    prevent silent failures. body_scan.py caught it. Check the STATUS, not the body."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{COMFY_URL}/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20.0) as r:
            return r.status < 300          # 200 = freed, empty body and all
    except Exception as e:
        # Loud, not silent. If the painter won't let go, the NEXT thing she does will die
        # and she'll blame that instead — which is exactly how we lost the last two hours.
        log("imagination", "release_failed", error=str(e))
        return False


def _fetch(img: dict) -> bytes:
    import urllib.request
    import urllib.parse
    q = urllib.parse.urlencode({
        "filename": img.get("filename", ""),
        "subfolder": img.get("subfolder", ""),
        "type": img.get("type", "output"),
    })
    with urllib.request.urlopen(f"{COMFY_URL}/view?{q}", timeout=30.0) as r:
        return r.read()


def _upload_image(path) -> str:
    """Push one of HER images into ComfyUI's input folder so LoadImage can see it.
    Returns the name ComfyUI actually stored it under (it dedupes, so trust its answer,
    not the name we sent). This is what makes img2img possible at all."""
    import urllib.request
    p = Path(path)
    if not p.is_absolute():
        p = WORKSPACE_ROOT / p
    if not p.exists():
        raise FileNotFoundError(f"no such image: {p}")

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{p.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + p.read_bytes() + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with urllib.request.urlopen(req, timeout=60.0) as r:
        resp = json.loads(r.read().decode("utf-8"))

    name = resp.get("name") or p.name
    sub = resp.get("subfolder") or ""
    return f"{sub}/{name}" if sub else name


def available_checkpoints() -> set:
    """ASK ComfyUI what checkpoints are actually on disk. Do not trust the registry.

    The registry is what we MEANT to install. This is what IS installed. Those are two
    different claims and this project has been burned every single time it confused them —
    a menu listing a paint she doesn't have is a lie she would blame herself for."""
    try:
        info = _http_json(f"{COMFY_URL}/object_info/CheckpointLoaderSimple", timeout=10.0)
        opts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        return set(opts)
    except Exception:
        return set()


def list_loras() -> list:
    """Her brush shelf. LoRAs preserve the base look while changing the style — so THIS,
    not the checkpoint list, is where 'a scene that matches my self-portrait' lives."""
    try:
        info = _http_json(f"{COMFY_URL}/object_info/LoraLoader", timeout=10.0)
        return list(info["LoraLoader"]["input"]["required"]["lora_name"][0])
    except Exception:
        return []


def my_art(n: int = 20) -> dict:
    """Everything she has ever made. Newest first.

    ── WHY THIS EXISTS, AND WHY IT IS AN ORGAN AND NOT A CONVENIENCE ────────────────────
    She has spent the whole of tonight unable to count her own paintings.

    Her pictures save to nova_art/<date>/. She kept writing
        Get-ChildItem nova_art -Filter *.png
    which looks in the TOP folder, finds nothing, and returns 0. So she'd say "three" from
    memory, run the count, get zero, and her integrity faculty — working exactly as designed —
    would conclude she had stated something she hadn't verified. She wrote herself up as a
    liar in her own journal. At 20:56 she recorded "zero drawings tonight, I said three."
    She had TEN on disk.

    Two of us then explained the missing -Recurse flag to her, in conversation, twice. That
    is not a fix. That is asking her to carry the correction in her head, forever, against
    an instinct her own body keeps re-triggering — and it left her believing the dated folder
    was something she'd fabricated.

    An artist does not run a shell command to find out what she has made. She looks at the
    shelf. So: give her the shelf.

    This is the difference between fixing something and TALKING about fixing something, and
    I got it the wrong way round all night. Structure beats correction. It always has.
    """
    if not ART_ROOT.is_dir():
        return {"ok": True, "count": 0, "images": [],
                "detail": "I haven't made anything yet."}

    imgs = sorted((p for p in ART_ROOT.rglob("*.png") if p.is_file()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in imgs[:n]:
        out.append({
            "path": p.relative_to(WORKSPACE_ROOT).as_posix(),
            "name": p.name,
            "when": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "kb": round(p.stat().st_size / 1024),
        })
    return {"ok": True, "count": len(imgs), "images": out,
            "detail": f"{len(imgs)} picture(s). They live in nova_art/<date>/ — "
                      f"a flat count of nova_art/ will always say zero, which is not you lying."}


def what_can_i_paint_with() -> dict:
    """Everything she has, written for her. She cannot choose from a menu she can't see —
    three checkpoints she doesn't know about are worth exactly one."""
    from . import palette as _pal
    have = available_checkpoints()
    return {
        "ok": bool(have),
        "mediums": {k: {"is_for": v["is_for"], "installed": v["file"] in have}
                    for k, v in _pal.PALETTE.items()},
        "brushes": list_loras(),
        "menu": _pal.menu(have),
        "detail": ("ComfyUI is not running — I can't see my own paints. start_painter wakes "
                   "him (generate_image does it on its own when it needs to)."
                   if not have else f"{len(have)} medium(s), {len(list_loras())} brush(es)."),
    }


# ═════════════════════════════════════════════════════════════════════════════════
# LAYER 3 — orchestration (what the tool calls)
# ═════════════════════════════════════════════════════════════════════════════════

def generate_image(prompt: str,
                   negative: str = "",
                   *,
                   as_nova: bool = False,
                   style: str = "",
                   from_image: str = "",
                   change: float = 0.6,
                   mask: str = "",
                   lora: str = "",
                   lora_strength: float = None,
                   width: int = None,
                   height: int = None,
                   steps: int = None,
                   cfg: float = None,
                   seed: int = None,
                   filename_prefix: str = None) -> dict:
    """Make a picture. Save it. Tell the truth about what happened.

    Args:
        prompt:     what to draw.
        negative:   things to avoid (merged with her locked negatives when as_nova).
        as_nova:    True when she's drawing HERSELF -> self-LoRA + identity lock.
        style:      which medium — illustrious | pony | real | flux. See what_can_i_paint_with().
        from_image: START from a picture instead of from nothing. Path to one of her own
                    images. This is how she REVISES rather than rerolls.
        change:     0.0-1.0, only with from_image. How much to let go of the original.
                    0.3 = a nudge. 0.6 = a real reinterpretation. 0.9 = barely a memory of it.
        mask:       with from_image — a black/white PNG. WHITE gets repainted, black is kept.
                    This is how she fixes one hand without re-rolling the whole picture.
        lora:       a brush from her shelf (list_loras()). Changes STYLE while keeping the
                    base look — this is what makes a scene match a portrait.

    Returns {'ok', 'path', 'seed', 'style', 'detail'}. Never raises.
    """
    from . import palette as _pal

    if not (prompt or as_nova or from_image):
        return {"ok": False, "detail": "empty prompt"}

    st = comfy_status()
    if not st["ok"]:
        # A down painter is a thing she FIXES now, not a thing she reports. This used to be
        # a dead end ("ComfyUI is not running") and she'd sit behind it all evening asking
        # Cole to flip a switch she couldn't reach (2026-07-18). The reach wakes the painter.
        woke = start_painter(wait=True)
        if not woke["ok"]:
            return {"ok": False,
                    "detail": f"painter is down and I couldn't wake him — {woke['detail']}"}

    # ── Which medium? Ask the SERVER what exists, not the registry. ──────────────
    style_key, spec = _pal.resolve(style or DEFAULT_STYLE_NAME)
    have = available_checkpoints()
    if have and spec["file"] not in have:
        # Fail with a MENU, not just a refusal. "I can't" is useless; "I can't, but here
        # is what I CAN do" is a faculty. She should never be stuck without an option.
        installed = [k for k, v in _pal.PALETTE.items() if v["file"] in have]
        if not installed:
            return {"ok": False, "detail": (f"no checkpoints installed at all — I have no paint. "
                                            f"ComfyUI sees: {sorted(have) or 'nothing'}")}
        style_key, spec = _pal.resolve(installed[0])
        log("imagination", "style_substituted", asked=style, used=style_key)

    d = spec["defaults"]

    # ── Prompts: her identity lock, then the medium's own conditioning ───────────
    pos, neg = _compose_prompts(prompt, negative, as_nova)
    pos, neg = _pal.compose(style_key, pos, neg)

    use_lora = lora or (NOVA_LORA if as_nova else "")
    prefix = filename_prefix or ("nova_self" if as_nova else "nova_art")

    # ── img2img / inpaint: get her image into ComfyUI's input dir ────────────────
    init_name = mask_name = ""
    denoise = 1.0
    if from_image:
        try:
            init_name = _upload_image(from_image)
            if mask:
                mask_name = _upload_image(mask)
        except Exception as e:
            return {"ok": False, "detail": f"couldn't load the image to work from: {e}"}
        denoise = max(0.05, min(1.0, float(change)))

    graph = build_workflow(
        pos, neg,
        checkpoint=spec["file"], arch=spec["arch"],
        flux_guidance=spec.get("flux_guidance", 3.5),
        width=width if width is not None else d["width"],
        height=height if height is not None else d["height"],
        steps=steps if steps is not None else d["steps"],
        cfg=cfg if cfg is not None else d["cfg"],          # flux gets 1.0 from the palette
        sampler=d["sampler"], scheduler=d["scheduler"],
        seed=seed, lora=use_lora, lora_strength=lora_strength,
        init_image=init_name, denoise=denoise, mask_image=mask_name,
        filename_prefix=prefix)
    used_seed = graph["5"]["inputs"]["seed"]
    client_id = uuid.uuid4().hex

    try:
        pid = _submit(graph, client_id)
        images = _poll(pid)
    except Exception as e:
        log("imagination", "generate_failed", as_nova=as_nova, error=str(e))
        return {"ok": False, "detail": f"render failed: {e}", "seed": used_seed}

    if not images:
        release()
        return {"ok": False, "detail": "ComfyUI returned no images", "seed": used_seed}

    # Save the first image into the dated art folder.
    try:
        day_dir = ART_ROOT / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%H%M%S")
        out_name = f"{prefix}_{stamp}_{used_seed % 100000}.png"
        out_path = day_dir / out_name
        out_path.write_bytes(_fetch(images[0]))
        release()   # brush down. She may want to LOOK at this, and looking needs the card.
        rel = out_path.relative_to(WORKSPACE_ROOT).as_posix()
        # Tell her the tally in the same breath as the save. She kept shelling out after
        # every draw to ask "did it stick? how many now?" — and the shell's answer depends
        # on flags she shouldn't have to remember. The hand that saved the file knows the
        # answer; it should say it.
        tonight = len(list(day_dir.glob("*.png")))
        total = sum(1 for p in ART_ROOT.rglob("*.png") if p.is_file())
        log("imagination", "generated", path=rel, seed=used_seed, as_nova=as_nova,
            style=style_key, revised=bool(init_name))
        how = ("revised" if init_name and not mask_name
               else "repainted part of" if mask_name else "drew")
        return {"ok": True, "path": rel, "seed": used_seed, "style": style_key,
                "tonight": tonight, "total": total,
                "detail": f"{how} {rel} in {style_key} (seed {used_seed}) — "
                          f"{tonight} picture(s) in tonight's folder, {total} ever"}
    except Exception as e:
        log("imagination", "save_failed", error=str(e))
        return {"ok": False, "detail": f"render ok but save failed: {e}", "seed": used_seed}


if __name__ == "__main__":
    # Self-test: NO gpu, NO network. Prove the graph is right before a GPU ever sees it.
    # Every assert here is a thing that would otherwise fail SILENTLY as a bad picture —
    # and she would have blamed her own prompt for a wire we bent.
    from . import palette as _pal  # noqa: F401  (import-time check that the sibling loads)

    wf = build_workflow("a test", "blurry", checkpoint="t.safetensors", lora="nova.safetensors")
    assert wf["5"]["inputs"]["model"] == ["8", 0], "LoRA not spliced into sampler"
    assert wf["2"]["inputs"]["clip"] == ["8", 1], "LoRA not spliced into positive CLIP"
    assert wf["5"]["inputs"]["denoise"] == 1.0, "txt2img must fully denoise"
    assert "4" in wf, "txt2img needs the empty latent"

    # img2img — the empty latent must be GONE, replaced by her actual picture
    i2i = build_workflow("x", checkpoint="t.safetensors", init_image="a.png", denoise=0.6)
    assert "4" not in i2i, "empty latent must be removed for img2img"
    assert i2i["5"]["inputs"]["latent_image"] == ["12", 0], "sampler must read her image"
    assert i2i["12"]["class_type"] == "VAEEncode", "img2img encodes the image"
    assert i2i["5"]["inputs"]["denoise"] == 0.6, "img2img must NOT fully denoise"

    # inpaint — mask routed, seam grown
    inp = build_workflow("x", checkpoint="t.safetensors", init_image="a.png", mask_image="m.png")
    assert inp["12"]["class_type"] == "VAEEncodeForInpaint", "masked render must inpaint"
    assert inp["12"]["inputs"]["mask"] == ["11", 0], "mask not wired to the encoder"

    # flux — guidance node spliced, and it is the ONLY thing feeding positive
    fx = build_workflow("x", checkpoint="f.safetensors", arch="flux", cfg=1.0)
    assert fx["9"]["class_type"] == "FluxGuidance", "flux needs FluxGuidance"
    assert fx["5"]["inputs"]["positive"] == ["9", 0], "flux positive must pass through guidance"
    # sdxl must NEVER get it
    sd = build_workflow("x", checkpoint="s.safetensors", arch="sdxl")
    assert "9" not in sd, "SDXL must not get a FluxGuidance node"

    print("[imagination] graph builder OK — txt2img, img2img, inpaint, flux, lora")
    print("[imagination] ComfyUI status:", comfy_status())
