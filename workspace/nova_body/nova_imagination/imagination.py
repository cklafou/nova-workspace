# Last updated: 2026-07-09 01:08:03
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

# The base checkpoint filename as it appears in ComfyUI/models/checkpoints/.
# Set NOVA_COMFY_CHECKPOINT once ComfyUI is installed (see the setup checklist).
BASE_CHECKPOINT = os.environ.get("NOVA_COMFY_CHECKPOINT", "")

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
                   width: int = None,
                   height: int = None,
                   steps: int = None,
                   cfg: float = None,
                   sampler: str = None,
                   scheduler: str = None,
                   seed: int = None,
                   lora: str = "",
                   lora_strength: float = None,
                   filename_prefix: str = "nova") -> dict:
    """Return a ComfyUI API-format graph (nodes keyed by string id) for a txt2img render.

    Pure function: builds and returns a dict, touches nothing. Optional LoraLoader is spliced
    between the checkpoint and the CLIP/sampler when `lora` is given (used for Nova's self-LoRA).
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
                         "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
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


# ═════════════════════════════════════════════════════════════════════════════════
# LAYER 3 — orchestration (what the tool calls)
# ═════════════════════════════════════════════════════════════════════════════════

def generate_image(prompt: str,
                   negative: str = "",
                   *,
                   as_nova: bool = False,
                   width: int = None,
                   height: int = None,
                   steps: int = None,
                   cfg: float = None,
                   seed: int = None,
                   filename_prefix: str = None) -> dict:
    """Render one image from a text prompt via ComfyUI and save it into the workspace.

    Args:
        prompt:   what to draw.
        negative: things to avoid (merged with Nova's locked negatives when as_nova).
        as_nova:  True when she's drawing HERSELF -> auto-apply self-LoRA + identity lock.
    Returns a result dict: {'ok', 'path', 'seed', 'detail'} (path is workspace-relative when ok).
    Never raises — returns {'ok': False, 'detail': ...} so the caller/Nova can reason about it.
    """
    if not (prompt or as_nova):
        return {"ok": False, "detail": "empty prompt"}
    if not BASE_CHECKPOINT:
        return {"ok": False, "detail": ("no base checkpoint configured — set NOVA_COMFY_CHECKPOINT "
                                        "to the checkpoint filename in ComfyUI/models/checkpoints/ "
                                        "(see the ComfyUI setup checklist).")}

    st = comfy_status()
    if not st["ok"]:
        return {"ok": False, "detail": f"ComfyUI is not running at {COMFY_URL}. {st['detail']}"}

    pos, neg = _compose_prompts(prompt, negative, as_nova)
    lora = NOVA_LORA if as_nova else ""
    prefix = filename_prefix or ("nova_self" if as_nova else "nova_art")

    graph = build_workflow(pos, neg, width=width, height=height, steps=steps, cfg=cfg,
                           seed=seed, lora=lora, filename_prefix=prefix)
    used_seed = graph["5"]["inputs"]["seed"]
    client_id = uuid.uuid4().hex

    try:
        pid = _submit(graph, client_id)
        images = _poll(pid)
    except Exception as e:
        log("imagination", "generate_failed", as_nova=as_nova, error=str(e))
        return {"ok": False, "detail": f"render failed: {e}", "seed": used_seed}

    if not images:
        return {"ok": False, "detail": "ComfyUI returned no images", "seed": used_seed}

    # Save the first image into the dated art folder.
    try:
        day_dir = ART_ROOT / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%H%M%S")
        out_name = f"{prefix}_{stamp}_{used_seed % 100000}.png"
        out_path = day_dir / out_name
        out_path.write_bytes(_fetch(images[0]))
        rel = out_path.relative_to(WORKSPACE_ROOT).as_posix()
        log("imagination", "generated", path=rel, seed=used_seed, as_nova=as_nova)
        return {"ok": True, "path": rel, "seed": used_seed,
                "detail": f"saved {rel} (seed {used_seed})"}
    except Exception as e:
        log("imagination", "save_failed", error=str(e))
        return {"ok": False, "detail": f"render ok but save failed: {e}", "seed": used_seed}


if __name__ == "__main__":
    # Self-test that needs NO gpu/network: prove the workflow builder is well-formed.
    wf = build_workflow("a test", "blurry", checkpoint="test.safetensors", lora="nova.safetensors")
    assert wf["5"]["inputs"]["model"] == ["8", 0], "LoRA not spliced into sampler"
    assert wf["2"]["inputs"]["clip"] == ["8", 1], "LoRA not spliced into positive CLIP"
    print("[imagination] workflow builder OK; nodes:", sorted(wf.keys()))
    print("[imagination] ComfyUI status:", comfy_status())
