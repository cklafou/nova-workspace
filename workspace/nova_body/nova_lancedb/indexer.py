# Last updated: 2026-10-04 14:28:11
"""Durable background memory ingestion with visible failures and bounded retries."""
import base64
import io
from pathlib import Path
import threading

from nova_runtime.work_queue import WorkQueue
from .hippocampus import get_store


class MemoryIndexer:
    def __init__(self, path=None, store_factory=None):
        self.queue = WorkQueue('memory', path)
        self._store_factory = store_factory or get_store
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True, name='MemoryIndexer')
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            if not self._thread.is_alive():
                self._thread = None

    def add_message(self, content, author, session_id=''):
        if content.strip():
            return self.queue.put({'type':'text','content':content,'author':author,
                                   'source':'chat','session_id':session_id})

    def add_image(self, image_data, caption, filename, session_id=''):
        if isinstance(image_data, Path):
            image_data = image_data.read_bytes()
        elif not isinstance(image_data, (str,bytes)):
            buf=io.BytesIO(); image_data.save(buf,format='PNG'); image_data=buf.getvalue()
        if isinstance(image_data,bytes):
            image_data='data:image/png;base64,'+base64.b64encode(image_data).decode('ascii')
        return self.queue.put({'type':'image','image_data':image_data,'caption':caption,
                               'filename':filename,'session_id':session_id})

    def process_one(self):
        job=self.queue.claim()
        if not job:
            return False
        try:
            item=job['payload']; store=self._store_factory()
            if item['type']=='text':
                ok=store.add_text(content=item['content'],author=item['author'],
                                  source=item['source'],session_id=item['session_id'],
                                  **({'timestamp':item['timestamp']} if 'timestamp' in item else {}))
            else:
                ok=store.add_image(image_input=item['image_data'],caption=item['caption'],
                                   filename=item['filename'],session_id=item['session_id'])
            if not ok:
                raise RuntimeError(getattr(store,'last_error',None) or 'Memory store rejected the write')
            self.queue.finish(job['id'])
        except Exception as e:
            self.queue.finish(job['id'],error=str(e))
            print(f'[nova_memory] Write retained for retry: {e}')
        return True

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                if not self.process_one():
                    self._stop_event.wait(1)
            except Exception as e:
                print(f'[nova_memory] Queue unavailable: {e}')
                self._stop_event.wait(2)

    def status(self):
        return {**self.queue.snapshot(), 'running':bool(self._thread and self._thread.is_alive())}


_indexer=None


def get_indexer():
    global _indexer
    if _indexer is None:
        _indexer=MemoryIndexer()
    return _indexer
