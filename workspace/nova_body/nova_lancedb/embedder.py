# @nova: Load cached semantic-memory embedders once per process and encode text/images without fabricating failed vectors.
# Last updated: 2026-10-05 18:23:37
"""
nova_lancedb/embedder.py
========================
Dual-modal embedding engine for Nova's memory store.

- Text:   all-MiniLM-L6-v2  (~22MB, 384-dim)  — fast semantic text search
- Visual: clip-ViT-B-32      (~350MB, 512-dim) — image / screenshot recall

Both models are lazy-loaded on first use and cached for the session.
If an embedding model fails, the caller retains the write for retry. A zero
vector must never be presented as a successfully indexed memory.
"""
from __future__ import annotations
import hashlib
import threading
import time
import numpy as np
from pathlib import Path
from typing import Optional

# ── Text embedder ────────────────────────────────────────────────────────────

_text_model = None
_text_model_lock = threading.Lock()
TEXT_DIM = 384


def _missing_local_assets(error):
    """Only cache absence permits the existing download fallback, never arbitrary failures."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if (type(error).__name__ == "LocalEntryNotFoundError"
                and type(error).__module__.startswith("huggingface_hub")):
            return True
        message = str(error).lower()
        if isinstance(error, OSError) and (
            "cannot find the requested files in the disk cache" in message
            or ("couldn't find" in message and "cached files" in message)
            or ("couldn't find" in message and "local cache" in message)
        ):
            return True
        error = error.__cause__ or error.__context__
    return False


def _construct_model(name):
    started = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    source = "local cache"
    try:
        model = SentenceTransformer(name, local_files_only=True)
    except Exception as error:
        if not _missing_local_assets(error):
            raise
        source = "missing-cache download fallback"
        model = SentenceTransformer(name)       # preserve existing first-install behavior
    print(f"[nova_memory] Embedder loaded ({name}; {source}; init={time.perf_counter() - started:.3f}s)")
    return model

def _load_text_model():
    global _text_model
    if _text_model is not None:
        return _text_model
    with _text_model_lock:
        if _text_model is not None:
            return _text_model
        try:
            _text_model = _construct_model("all-MiniLM-L6-v2")
        except Exception as error:
            print(f"[nova_memory] WARNING: text embedder failed to load: {error}")
            _text_model = None
    return _text_model


def embed_text(text: str) -> list[float]:
    """Return a 384-dim embedding for a text string."""
    model = _load_text_model()
    if model is None:
        return _null_vec(TEXT_DIM)
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        print(f"[nova_memory] embed_text error: {e}")
        return _null_vec(TEXT_DIM)


# ── Visual embedder ──────────────────────────────────────────────────────────

_clip_model = None
_clip_model_lock = threading.Lock()
VISUAL_DIM = 512

def _load_clip_model():
    global _clip_model
    if _clip_model is not None:
        return _clip_model
    with _clip_model_lock:
        if _clip_model is not None:
            return _clip_model
        try:
            _clip_model = _construct_model("clip-ViT-B-32")
        except Exception as error:
            print(f"[nova_memory] WARNING: visual embedder failed to load: {error}")
            _clip_model = None
    return _clip_model


def embed_image(image_input) -> list[float]:
    """
    Return a 512-dim CLIP embedding for an image.
    image_input can be:
      - PIL.Image.Image
      - str / Path  (file path)
      - bytes       (raw bytes, decoded internally)
      - str         (base64 data URL — prefix stripped automatically)
    """
    model = _load_clip_model()
    if model is None:
        return _null_vec(VISUAL_DIM)
    try:
        from PIL import Image
        import io, base64

        if isinstance(image_input, str) and image_input.startswith("data:"):
            # Strip data URL prefix: "data:image/png;base64,<b64>"
            _, b64 = image_input.split(",", 1)
            image_input = Image.open(io.BytesIO(base64.b64decode(b64)))
        elif isinstance(image_input, bytes):
            image_input = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, (str, Path)):
            image_input = Image.open(image_input)

        if hasattr(image_input, "convert"):
            image_input = image_input.convert("RGB")

        vec = model.encode(image_input, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        print(f"[nova_memory] embed_image error: {e}")
        return _null_vec(VISUAL_DIM)


def embed_text_for_visual(text: str) -> list[float]:
    """
    Embed text in CLIP's visual space so you can search visual memories with words.
    e.g. embed_text_for_visual("trading chart with red candles")
    """
    model = _load_clip_model()
    if model is None:
        return _null_vec(VISUAL_DIM)
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        print(f"[nova_memory] embed_text_for_visual error: {e}")
        return _null_vec(VISUAL_DIM)


# ── Utility ──────────────────────────────────────────────────────────────────

def _null_vec(dim: int) -> list[float]:
    raise RuntimeError(f"The {dim}-dimension embedder is unavailable or failed; no valid vector was produced")


def content_hash(content: str) -> str:
    """Deterministic short hash for dedup checking."""
    return hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()[:12]
