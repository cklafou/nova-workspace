# @nova: NovaRuntime — her life-support engine (layer 2 of the three-layer model).
#        Holds the event bus + transcript store now; later steps relocate the autonomy
#        daemon, model client, memory indexer, sense population, and llama health/restart
#        (and KoELS equip/self-restart) into here. Boots with NO chat server attached —
#        a face subscribes to the bus when present. THIS is what makes "she lives and
#        works whether or not anyone's watching the chat" real instead of aspirational.
"""
nova_runtime/runtime.py — the runtime body part (skeleton, Step 1 of the extraction).

What's here now: the seams (event bus + transcript store) and a headless boot that proves
the pluck test — she comes up, perceives, and idles with zero interaction surface.

What is NOT here yet (relocated in later steps, slots marked below): the autonomy daemon,
her model client, the memory indexer, sense population, llama health/autostart/restart.
Those still live in general_tools/nova_chat/server.py and keep working there until each is
moved — we build alongside and pluck-test before flipping the default boot.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from nova_runtime.event_bus import EventBus
from nova_runtime.transcript_store import TranscriptStore
from nova_runtime.llama_control import LlamaControl
from nova_runtime.model_guard import ModelGuard
from nova_runtime.model_client import ModelClient

_WORKSPACE = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
              else Path(__file__).resolve().parent.parent.parent)


class NovaRuntime:
    def __init__(self, workspace=None, transcript_path=None):
        self.workspace = Path(workspace) if workspace else _WORKSPACE
        self.bus = EventBus()
        tpath = transcript_path or (self.workspace / "logs" / "runtime" / "transcript.jsonl")
        self.transcript = TranscriptStore(log_path=tpath)
        self._running = False

        # ── STEP 2 (done): model-server life-support + model-call guard now live here ──
        self.llama = LlamaControl(self.workspace)   # health / autostart / stop / restart (+ KoELS equip later)
        self.guard = ModelGuard()                   # rate-limit failsafe + consecutive-llama-error backoff

        # ── STEP 4 (done): the model-dispatch faculty — owns WHICH client + HOW it's driven.
        #    A host registers the client modules (model_client.register); the faculty stays
        #    import-clean of any chat-server module so generation survives the pluck. ──
        self.model_client = ModelClient()

        # ── slots filled by later extraction steps (kept in server.py until then) ──
        self.indexer = None          # STEP 3: nova_lancedb memory indexer
        self._daemon_task = None     # STEP 5: the autonomy daemon, moved onto the bus

    # ── face attach/detach (a face is optional; detaching never stops the runtime) ──

    def attach_face(self) -> asyncio.Queue:
        """A face (e.g. the chat server) calls this to receive runtime events to render."""
        return self.bus.subscribe()

    def detach_face(self, q: asyncio.Queue) -> None:
        self.bus.unsubscribe(q)

    # ── perception passthrough (the daemon will use these once relocated) ──

    def cole_pending(self) -> bool:
        """Has Cole spoken something Nova hasn't attended? Reads the durable transcript,
        not any face's memory — works with the chat server plucked."""
        self.transcript.reload_from_disk()
        return self.transcript.has_unread_cole()

    async def emit(self, event: str, text: str, level: str = "info", **extra) -> None:
        """Publish a lifecycle event to any attached face AND append it to the durable
        event log. Never depends on a face existing (seam #1)."""
        payload = {"type": "nova_event", "event": event, "text": text,
                   "level": level, "ts": datetime.now().isoformat()}
        payload.update(extra)
        await self.bus.publish(payload)
        try:
            ev_dir = self.workspace / "logs" / "events"
            ev_dir.mkdir(parents=True, exist_ok=True)
            import json
            with open(ev_dir / f"events-{datetime.now().strftime('%Y-%m-%d')}.jsonl",
                      "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── STEP 3: memory indexing + proprioception (body-owned; a face just reads/relays) ──

    def start_indexer(self) -> bool:
        """Bring up her semantic-memory indexer (nova_lancedb). Owned by the runtime so
        memory indexing survives with no chat server attached. None-safe if unavailable."""
        try:
            from nova_lancedb.indexer import get_indexer
            self.indexer = get_indexer()
            self.indexer.start()
            return True
        except Exception as e:
            self.indexer = None
            print(f"[nova_runtime] memory indexer unavailable: {e}")
            return False

    def stop_indexer(self) -> None:
        if self.indexer:
            try:
                self.indexer.stop()
            except Exception:
                pass

    def index_message(self, content: str, author: str, session_id) -> None:
        """Index one message into semantic memory; no-op if the indexer isn't up."""
        if self.indexer:
            try:
                self.indexer.add_message(content, author, session_id)
            except Exception:
                pass

    def read_system_metrics(self) -> dict:
        """Proprioception — CPU / RAM / VRAM. Best-effort: a missing tool degrades to a
        partial dict rather than raising. Relocated from the chat server's _bg_sys_metrics;
        a face polls this and decides whether to display it."""
        m: dict = {}
        try:
            import psutil
            m["cpu_pct"] = round(psutil.cpu_percent(interval=None), 1)
            vm = psutil.virtual_memory()
            m["ram_gb"] = round(vm.used / (1024 ** 3), 1)
            m["ram_total"] = round(vm.total / (1024 ** 3), 1)
        except Exception:
            pass
        try:
            import subprocess
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                parts = r.stdout.strip().split(",")
                if len(parts) == 2:
                    used_mb, total_mb = int(parts[0].strip()), int(parts[1].strip())
                    m["vram"] = f"{used_mb // 1024}/{total_mb // 1024} GB"
                    m["vram_pct"] = round(used_mb / total_mb * 100, 1)
        except Exception:
            pass
        return m

    # ── lifecycle ──

    async def run(self) -> None:
        """Headless boot. Step 1: stand up the seams and idle, proving she lives with no
        face. Later steps add (here): llama health-gate → memory indexer → senses →
        autonomy daemon. The chat server, when present, just attaches to self.bus."""
        self._running = True
        await self.emit("boot", "Nova runtime up — headless (no chat server attached)")
        print(f"[nova_runtime] up. workspace={self.workspace} "
              f"faces={self.bus.subscriber_count()} (0 = headless, healthy)")
        # LATER: await self._start_llama_healthgate(); self._start_indexer();
        #        self._populate_senses(); self._daemon_task = asyncio.ensure_future(self._autonomy_daemon())
        while self._running:
            await asyncio.sleep(1)

    def stop(self) -> None:
        self._running = False
