# Last updated: 2026-07-09 05:14:59
"""
nova_lancedb/embedder.py
========================
Dual-modal embedding engine for Nova's memory store.

- Text:   all-MiniLM-L6-v2  (~22MB, 384-dim)  — fast semantic text search
- Visual: clip-ViT-B-32      (~350MB, 512-dim) — image / screenshot recall

Both models are lazy-loaded on first use and cached for the session.
If a model fails to load (e.g., no internet, OOM), falls back to a null
embedding so the rest of the system continues without crashing.
"""
from __future__ import annotations
import hashlib
import numpy as np
from pathlib import Path
from typing import Optional

# ── Text embedder ────────────────────────────────────────────────────────────

_text_model = None
TEXT_DIM = 384

def _load_text_model():
    global _text_model
    if _text_model is not None:
        return _text_model
    try:
        from sentence_transformers import SentenceTransformer
        _text_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[nova_memory] Text embedder loaded (all-MiniLM-L6-v2)")
    except Exception as e:
        print(f"[nova_memory] WARNING: text embedder failed to load: {e}")
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
VISUAL_DIM = 512

def _load_clip_model():
    global _clip_model
    if _clip_model is not None:
        return _clip_model
    try:
        from sentence_transformers import SentenceTransformer
        _clip_model = SentenceTransformer("clip-ViT-B-32")
        print("[nova_memory] Visual embedder loaded (clip-ViT-B-32)")
    except Exception as e:
        print(f"[nova_memory] WARNING: visual embedder failed to load: {e}")
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
    return [0.0] * dim


def content_hash(content: str) -> str:
    """Deterministic short hash for dedup checking."""
    return hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()[:12]
