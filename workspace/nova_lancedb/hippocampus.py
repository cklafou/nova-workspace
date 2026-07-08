# Last updated: 2026-07-08 21:01:20
"""
nova_lancedb/hippocampus.py — Semantic + Episodic Memory Store
==============================================================
Renamed from store.py (Step 2 anatomical restructure, 2026-05-08).
LanceDB-backed sovereign memory store for Nova.

Two tables:
  nova_text    — conversation turns, notes, file knowledge  (384-dim MiniLM)
  nova_visual  — screenshots, image attachments, video frames (512-dim CLIP)

Design principles:
  • Disk-native: only loads the relevant fragment on each query, not the whole DB
  • Dedup: content-hash check prevents storing the same memory twice
  • Category-tagged: auto-categorised so Nova can filter (financial, technical, etc.)
  • Session-aware: each conversation has a session_id for pruning old sessions
  • Graceful degradation: if LanceDB or embedder fails, NovaMemoryStore silently
    no-ops — the rest of the server keeps working
"""
from __future__ import annotations

import os
import time
import uuid
import re
from pathlib import Path
from typing import Optional

# ── DB Path ──────────────────────────────────────────────────────────────────

WORKSPACE_DIR = (
    Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent
)
DB_PATH = str(WORKSPACE_DIR / "nova_memory_db")

# ── Category rules ───────────────────────────────────────────────────────────

_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("financial",  re.compile(r"\b(trading|stock|ticker|thinkorswim|position|portfolio|"
                               r"market|candle|chart|option|futures|pnl|profit|loss|"
                               r"wallet|crypto|bitcoin|price|spread|leverage)\b", re.I)),
    ("technical",  re.compile(r"\b(python|server|llama|code|bug|fix|error|deploy|"
                               r"function|class|import|api|endpoint|script|cuda|gpu|"
                               r"vram|gguf|token|model|inference|prompt|lancedb)\b", re.I)),
    ("project",    re.compile(r"\b(nova|egpu|oculink|project nova|sovereign|"
                               r"nova_chat|llama\.cpp|qwen)\b", re.I)),
    ("personal",   re.compile(r"\b(cole|feeling|day|relationship|goal|coffee|morning|"
                               r"night|tired|excited|sleep|friend|family|mood)\b", re.I)),
]


def _classify(text: str) -> str:
    for cat, pat in _CATEGORY_RULES:
        if pat.search(text):
            return cat
    return "general"


# ── Schema helpers ───────────────────────────────────────────────────────────

def _text_schema():
    import pyarrow as pa
    return pa.schema([
        pa.field("id",          pa.utf8()),
        pa.field("content",     pa.utf8()),
        pa.field("vector",      pa.list_(pa.float32(), 384)),
        pa.field("category",    pa.utf8()),
        pa.field("source",      pa.utf8()),
        pa.field("session_id",  pa.utf8()),
        pa.field("author",      pa.utf8()),
        pa.field("content_hash",pa.utf8()),
        pa.field("timestamp",   pa.float64()),
    ])


def _visual_schema():
    import pyarrow as pa
    return pa.schema([
        pa.field("id",          pa.utf8()),
        pa.field("caption",     pa.utf8()),
        pa.field("vector",      pa.list_(pa.float32(), 512)),
        pa.field("category",    pa.utf8()),
        pa.field("source",      pa.utf8()),
        pa.field("session_id",  pa.utf8()),
        pa.field("filename",    pa.utf8()),
        pa.field("content_hash",pa.utf8()),
        pa.field("timestamp",   pa.float64()),
    ])


# ── NovaMemoryStore ───────────────────────────────────────────────────────────

class NovaMemoryStore:
    """
    Persistent, disk-native memory for Nova.
    Thread-safe for reads; writes should be done from a single background thread
    (the MemoryIndexer handles this).
    """

    def __init__(self):
        self._db = None
        self._text_tbl = None
        self._visual_tbl = None
        self._known_hashes: set[str] = set()  # in-memory dedup cache
        self._ready = False
        self._init()

    def _init(self):
        try:
            import lancedb
            self._db = lancedb.connect(DB_PATH)
            self._text_tbl   = self._open_or_create("nova_text",   _text_schema())
            self._visual_tbl = self._open_or_create("nova_visual", _visual_schema())
            # Warm the dedup cache
            try:
                rows = self._text_tbl.to_pandas()["content_hash"].tolist()
                self._known_hashes.update(rows)
                rows_v = self._visual_tbl.to_pandas()["content_hash"].tolist()
                self._known_hashes.update(rows_v)
            except Exception:
                pass
            self._ready = True
            print(f"[nova_memory] DB ready at {DB_PATH}")
        except Exception as e:
            print(f"[nova_memory] WARNING: DB init failed — {e}. Memory disabled.")

    def _open_or_create(self, name: str, schema):
        existing = self._db.table_names()
        if name in existing:
            return self._db.open_table(name)
        return self._db.create_table(name, schema=schema)

    # ── Text memory ──────────────────────────────────────────────────────────

    def add_text(self, content: str, author: str = "Nova",
                 source: str = "chat", session_id: str = "",
                 category: str = "") -> bool:
        """Embed and store a text memory. Returns True if stored, False if duplicate/error."""
        if not self._ready or not content.strip():
            return False
        from .embedder import embed_text, content_hash
        chash = content_hash(content)
        if chash in self._known_hashes:
            return False
        try:
            vec  = embed_text(content)
            cat  = category or _classify(content)
            row  = {
                "id":           str(uuid.uuid4()),
                "content":      content[:4000],  # cap to avoid giant rows
                "vector":       vec,
                "category":     cat,
                "source":       source,
                "session_id":   session_id,
                "author":       author,
                "content_hash": chash,
                "timestamp":    time.time(),
            }
            self._text_tbl.add([row])
            self._known_hashes.add(chash)
            return True
        except Exception as e:
            print(f"[nova_memory] add_text error: {e}")
            return False

    def search_text(self, query: str, top_k: int = 8,
                    category: Optional[str] = None) -> list[dict]:
        """Semantic search over text memories. Returns list of dicts."""
        if not self._ready:
            return []
        from .embedder import embed_text
        try:
            vec = embed_text(query)
            tbl = self._text_tbl.search(vec).limit(top_k)
            if category:
                tbl = tbl.where(f"category = '{category}'")
            rows = tbl.to_list()
            # Remove the raw vector from results (too noisy)
            for r in rows:
                r.pop("vector", None)
            return rows
        except Exception as e:
            print(f"[nova_memory] search_text error: {e}")
            return []

    # ── Visual memory ─────────────────────────────────────────────────────────

    def add_image(self, image_input, caption: str = "",
                  filename: str = "", session_id: str = "",
                  category: str = "") -> bool:
        """Embed and store an image memory. image_input: PIL, path, bytes, or data URL."""
        if not self._ready:
            return False
        from .embedder import embed_image, content_hash
        chash = content_hash(caption + filename)
        if chash in self._known_hashes:
            return False
        try:
            vec  = embed_image(image_input)
            cat  = category or _classify(caption)
            row  = {
                "id":           str(uuid.uuid4()),
                "caption":      caption[:2000],
                "vector":       vec,
                "category":     cat,
                "source":       "image_attachment",
                "session_id":   session_id,
                "filename":     filename,
                "content_hash": chash,
                "timestamp":    time.time(),
            }
            self._visual_tbl.add([row])
            self._known_hashes.add(chash)
            return True
        except Exception as e:
            print(f"[nova_memory] add_image error: {e}")
            return False

    def search_visual(self, query: str, top_k: int = 5) -> list[dict]:
        """Search visual memories using a text query (cross-modal CLIP search)."""
        if not self._ready:
            return []
        from .embedder import embed_text_for_visual
        try:
            vec  = embed_text_for_visual(query)
            rows = self._visual_tbl.search(vec).limit(top_k).to_list()
            for r in rows:
                r.pop("vector", None)
            return rows
        except Exception as e:
            print(f"[nova_memory] search_visual error: {e}")
            return []

    # ── Context builder ───────────────────────────────────────────────────────

    def build_context_block(self, query: str, max_chars: int = 4000) -> str:
        """
        Build a context block to inject into Nova's system prompt.
        Combines top text memories + top visual memories for the query.
        Returns empty string if nothing useful found.
        """
        if not self._ready:
            return ""

        text_hits   = self.search_text(query,   top_k=6)
        visual_hits = self.search_visual(query, top_k=3)

        if not text_hits and not visual_hits:
            return ""

        lines = ["--- NOVA PERSISTENT MEMORY (most relevant to this conversation) ---"]

        for hit in text_hits:
            ts   = hit.get("timestamp", 0)
            age  = _age_str(ts)
            src  = hit.get("source", "")
            auth = hit.get("author", "")
            cat  = hit.get("category", "")
            text = hit.get("content", "")
            lines.append(f"[{cat}|{src}|{age}] {auth}: {text[:600]}")

        if visual_hits:
            lines.append("--- VISUAL MEMORIES ---")
            for hit in visual_hits:
                ts  = hit.get("timestamp", 0)
                age = _age_str(ts)
                cap = hit.get("caption", "(no caption)")
                fn  = hit.get("filename", "")
                lines.append(f"[visual|{age}] {fn}: {cap[:300]}")

        lines.append("--- END PERSISTENT MEMORY ---")

        block = "\n".join(lines)
        if len(block) > max_chars:
            block = block[:max_chars] + "\n[... memory truncated]"
        return block

    # ── Maintenance ───────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        if not self._ready:
            return {"ready": False}
        try:
            return {
                "ready":       True,
                "text_count":  self._text_tbl.count_rows(),
                "visual_count":self._visual_tbl.count_rows(),
                "db_path":     DB_PATH,
            }
        except Exception:
            return {"ready": True, "text_count": -1, "visual_count": -1}

    def clear_session(self, session_id: str):
        """Delete all memories for a given session (chat cleanup)."""
        if not self._ready or not session_id:
            return
        try:
            self._text_tbl.delete(f"session_id = '{session_id}'")
            self._visual_tbl.delete(f"session_id = '{session_id}'")
        except Exception as e:
            print(f"[nova_memory] clear_session error: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _age_str(ts: float) -> str:
    if not ts:
        return "unknown"
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff/60)}m ago"
    if diff < 86400:
        return f"{int(diff/3600)}h ago"
    return f"{int(diff/86400)}d ago"


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: Optional[NovaMemoryStore] = None

def get_store() -> NovaMemoryStore:
    global _store
    if _store is None:
        _store = NovaMemoryStore()
    return _store
