# Last updated: 2026-07-08 19:59:44
"""
nova_lancedb/indexer.py
======================
Background indexer for Nova's persistent memory.

Provides a thread-safe queue to ingest new chat messages and workspace
documents into the LanceDB store without blocking the main event loops.
"""
import asyncio
import queue
import threading
import time
from pathlib import Path

from .hippocampus import get_store

class MemoryIndexer:
    def __init__(self):
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background indexing thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        
        # Ensure store is initialized on the worker thread too, or before starting
        get_store()
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="MemoryIndexer")
        self._thread.start()
        print("[nova_memory] Indexer thread started.")

    def stop(self):
        """Stop the background indexing thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        print("[nova_memory] Indexer thread stopped.")

    def add_message(self, content: str, author: str, session_id: str = ""):
        """Queue a generic message for indexing."""
        if not content.strip():
            return
        self._queue.put({
            "type": "text",
            "content": content,
            "author": author,
            "source": "chat",
            "session_id": session_id,
        })
        
    def add_image(self, image_data, caption: str, filename: str, session_id: str = ""):
        """Queue an image for indexing."""
        self._queue.put({
            "type": "image",
            "image_data": image_data,
            "caption": caption,
            "filename": filename,
            "session_id": session_id,
        })

    def _worker(self):
        store = get_store()
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                if item["type"] == "text":
                    store.add_text(
                        content=item["content"],
                        author=item["author"],
                        source=item["source"],
                        session_id=item["session_id"]
                    )
                elif item["type"] == "image":
                    store.add_image(
                        image_input=item["image_data"],
                        caption=item["caption"],
                        filename=item["filename"],
                        session_id=item["session_id"]
                    )
            except Exception as e:
                print(f"[nova_memory] Indexer error processing item: {e}")
            finally:
                self._queue.task_done()

# ── Singleton ──

_indexer = None

def get_indexer() -> MemoryIndexer:
    global _indexer
    if _indexer is None:
        _indexer = MemoryIndexer()
    return _indexer
