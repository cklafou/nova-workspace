# Last updated: 2026-07-08 22:03:10
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
from nova_runtime.koels_equip import KoELSEquip

_WORKSPACE = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
              else Path(__file__).resolve().parent.parent.parent)


class _TickContext:
    """A single-tick generation context for headless autonomy (mirrors the chat server's
    HeartbeatContext): NO chat history, just this tick's prompt + any injected workspace
    context. Gives nova_client the `.to_messages(...)` shape it expects without dragging in
    the server's session objects — so her body can generate with no face attached."""
    def __init__(self, tick: str):
        self._tick = tick

    def to_messages(self, ai_name: str, system_prefix: str = "",
                    workspace_context: str = "") -> list[dict]:
        sys_content = (system_prefix or "").strip()
        if workspace_context:
            sys_content += (f"\n\n--- WORKSPACE CONTEXT ---\n{workspace_context}\n"
                            "--- END CONTEXT ---")
        return [{"role": "system", "content": sys_content},
                {"role": "user", "content": self._tick}]


class NovaRuntime:
    def __init__(self, workspace=None, transcript_path=None):
        self.workspace = Path(workspace) if workspace else _WORKSPACE
        self.bus = EventBus()
        tpath = transcript_path or (self.workspace / "logs" / "runtime" / "transcript.jsonl")
        self.transcript = TranscriptStore(log_path=tpath)
        self._running = False

        # ── STEP 2 (done): model-server life-support + model-call guard now live here ──
        self.llama = LlamaControl(self.workspace, launcher="start_llama_qwen36.cmd")   # Qwen 3.6 + MTP launcher (KoELS --lora hook built in); was start_llama.cmd (3.5)
        self.guard = ModelGuard()                   # rate-limit failsafe + consecutive-llama-error backoff

        # ── STEP 4 (done): the model-dispatch faculty — owns WHICH client + HOW it's driven.
        #    A host registers the client modules (model_client.register); the faculty stays
        #    import-clean of any chat-server module so generation survives the pluck. ──
        self.model_client = ModelClient()

        # ── KoELS equip mechanism (skeleton): the runtime-side physical act of wearing a
        #    specialist loadout — composes LlamaControl. The launcher's --lora consumption is
        #    live-gated (quick -fa/VRAM check + a real adapter); the logic is built + tested. ──
        self.koels = KoELSEquip(self.workspace, self.llama)

        # ── slots filled by later extraction steps (kept in server.py until then) ──
        self.indexer = None          # STEP 3: nova_lancedb memory indexer
        self._daemon_task = None     # STEP 6c: headless autonomy task handle
        self._autonomy_stop = False  # STEP 6b: cooperative stop flag for run_autonomy

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
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
            if r.returncode == 0:
                parts = r.stdout.strip().split(",")
                if len(parts) == 2:
                    used_mb, total_mb = int(parts[0].strip()), int(parts[1].strip())
                    m["vram"] = f"{used_mb // 1024}/{total_mb // 1024} GB"
                    m["vram_pct"] = round(used_mb / total_mb * 100, 1)
        except Exception:
            pass
        return m

    # ── STEP 5: sense population (body-owned). The runtime populates her Touch sense — what is
    #    interacting with her right now — so she can FEEL it during reflection. The host passes
    #    only the face-state it alone knows (viewers, eyes); cole_typing + surfaces are read from
    #    her own environment/memory here. The daemon (still hosted in the chat server for now)
    #    calls these; once the loop relocates (Step 6) they're called from inside her body. ──

    def surfaces_from_layout(self) -> list:
        """The UI widget ids she's currently 'looked at' through — read from her own
        memory/ui_layout.json. Best-effort; empty list if absent/unreadable."""
        try:
            import json as _json
            lf = self.workspace / "memory" / "ui_layout.json"
            if lf.exists():
                widgets = _json.loads(lf.read_text(encoding="utf-8")).get("widgets") or []
                return [w.get("id") for w in widgets if w.get("id")]
        except Exception:
            pass
        return []

    def populate_touch(self, *, viewers: int = 0, agents_online: list = None,
                       eyes_streaming: bool = False, who: str = None, what: str = None,
                       autonomy_active: bool = True) -> None:
        """Update her Touch sense + (optionally) record who is pulling on her this moment.
        cole_typing + surfaces come from her own senses/memory; viewers/eyes/agents are the
        face-state the host supplies. Best-effort — a missing senses module never breaks a tick."""
        try:
            from nova_senses import touch as _touch, environment as _env
            _touch.update(viewers=viewers, cole_typing=_env.cole_typing(),
                          agents_online=agents_online or [], eyes_streaming=eyes_streaming,
                          autonomy_active=autonomy_active, surfaces=self.surfaces_from_layout())
            if who is not None:
                _touch.record_pull(who, what or "")
        except Exception as e:
            print(f"[nova_runtime] touch populate failed: {e}")

    def clear_touch_active(self) -> None:
        """Tick over — she's no longer actively engaged. Best-effort."""
        try:
            from nova_senses import touch as _touch
            _touch.update(autonomy_active=False)
        except Exception:
            pass

    # ── lifecycle ──

    async def run(self) -> None:
        """Headless boot — THE pluck test. Brings her up with NO chat server attached: her
        model server live, semantic memory indexing, and her autonomy loop ticking — all on
        her own. A face (the chat server), if it ever attaches, just subscribes to self.bus.
        This is what `python -m nova_runtime` runs. Step 6c."""
        self._running = True
        await self.emit("boot", "Nova runtime up — headless (no chat server attached)")
        # 1) her model server — bring it up if it isn't already
        try:
            print(f"[nova_runtime] llama autostart → {self.llama.autostart()}")
        except Exception as e:
            print(f"[nova_runtime] llama autostart failed: {e}")
        # 2) her semantic memory
        self.start_indexer()
        # 3) her model client. nova_client is a leaf module (stdlib + httpx, no chat-server
        #    deps), so importing it here doesn't drag the server in. Fully relocating it into
        #    the body is a later cleanup for a perfect pluck; for now this is enough to think.
        try:
            from nova_chat.clients import nova as _nova
            self.model_client.register({"Nova": _nova})
        except Exception as e:
            print(f"[nova_runtime] model client unavailable (headless generation off): {e}")
        # 4) fresh-start perception: don't re-answer Cole messages that predate this boot
        try:
            self.transcript.reload_from_disk()
            self.transcript.mark_attended_through(self.transcript.last_seq("Cole"))
        except Exception:
            pass
        # 5) coordination primitives (runtime-local when headless)
        self._force_wake = asyncio.Event()
        self._stop_req = asyncio.Event()
        self._busy = False
        # 6) her cognition loop, driven with runtime-native hooks (no server needed)
        self._daemon_task = asyncio.ensure_future(self.run_autonomy(
            perceive_cole_pending=self._perceive_cole_headless,
            recent_context=self._recent_text_headless,
            model_available=self._model_up_headless,
            generate=self._generate_headless,
            is_busy=lambda: self._busy,
            set_busy=self._set_busy_headless,
            face_state=None,
            force_wake=self._force_wake,
            stop_requested=self._stop_req,
        ))
        print(f"[nova_runtime] headless up. workspace={self.workspace} "
              f"faces={self.bus.subscriber_count()} (0 = headless, healthy)")
        while self._running:
            await asyncio.sleep(1)

    def stop(self) -> None:
        self._running = False
        self.stop_autonomy()

    # ── STEP 6b: the sleep/wake cognition loop, relocated from the chat server. The body now
    #    OWNS the loop; a host supplies only the I/O it alone has (chat perception, the model
    #    call, the shared busy flag, face-state). Cognition (executive/tasking) and her senses
    #    are imported directly — they're her faculties, not the server's. Lifecycle events go
    #    out on her bus, so a face renders them and a plucked server changes nothing. The
    #    headless launcher (Step 6c) will call run_autonomy with runtime-native hooks; for now
    #    the chat server drives it with its own. ──

    async def run_autonomy(self, *, perceive_cole_pending, recent_context, model_available,
                           generate, is_busy, set_busy, face_state=None,
                           force_wake=None, stop_requested=None,
                           poll_idle: float = 3.0, poll_forced: float = 0.5,
                           poll_disabled: float = 2.0, model_retry: float = 5.0) -> None:
        """Persistent sleep/wake loop (faithful relocation of the server's autonomy_daemon).

        Host-supplied hooks:
          perceive_cole_pending() -> bool          has Cole spoken unanswered (chat perception)
          recent_context() -> str                  recent conversation handed to her reflection
          model_available() -> awaitable[bool]     is her model reachable
          generate(prompt, cole_pending) -> awaitable[str]   one model turn in her voice
          is_busy() -> bool / set_busy(bool)       the shared busy flag (host owns it in 6b)
          face_state() -> dict                     {viewers, agents_online, eyes_streaming}; optional
          force_wake / stop_requested              Event-likes (is_set/clear); optional
        Cognition + senses are hers, imported here. Exits cleanly when stop_autonomy() is called."""
        from nova_cortex import executive
        self._autonomy_stop = False
        await asyncio.sleep(2)
        while not self._autonomy_stop:
            forced = bool(force_wake and force_wake.is_set())
            if not forced and not executive.autonomy_enabled():
                await asyncio.sleep(poll_disabled)
                continue
            await asyncio.sleep(poll_forced if forced else poll_idle)   # ASLEEP — cheap poll, no model
            if (stop_requested and stop_requested.is_set()) or is_busy():
                continue                              # busy — leave force_wake set; handle next loop
            cole_pending = perceive_cole_pending()
            # standing-directive release: a directive's job is to make her attend Cole's word
            # ONCE; if she's already the last speaker, release it so it doesn't re-wake her.
            if not cole_pending:
                try:
                    from nova_senses import environment as _env
                    if _env.cole_directive():
                        _env.consume_cole_directive()
                except Exception:
                    pass
            if forced:
                if force_wake:
                    force_wake.clear()
                should, reason = True, "Cole pressed Wake Up"
            else:
                should, reason = executive.should_wake(cole_pending)
            if not should:
                continue
            try:
                if not await model_available():
                    await asyncio.sleep(model_retry)
                    continue
            except Exception:
                await asyncio.sleep(model_retry)
                continue
            await self._run_one_wake(reason, forced, cole_pending,
                                     recent_context, generate, set_busy, face_state)

    async def _run_one_wake(self, reason, forced, cole_pending,
                            recent_context, generate, set_busy, face_state) -> None:
        """One wake: reflect → decide → (maybe) execute. Sleep-free, so it's unit-testable in
        isolation. Faithful to the server's two-phase wake + execution pass; lifecycle signals
        go out on her bus (self.emit + processing_start/end published to the bus)."""
        from nova_cortex import executive
        await self.emit("wake", f"Nova woke — {reason}")
        # ── Two-phase wake: she SITS WITH the moment (reflect) before she may act ──
        set_busy(True)
        await self.bus.publish({"type": "processing_start"})
        try:
            recent = recent_context()
            # Populate Touch — what's interacting with her right now — so she can FEEL it during
            # reflection. The host passes only the face-state it alone knows (viewers/eyes/agents).
            fs = (face_state() if face_state else None) or {}
            self.populate_touch(
                viewers=fs.get("viewers", 0), agents_online=fs.get("agents_online", []),
                eyes_streaming=fs.get("eyes_streaming", False),
                who=("Cole" if cole_pending else "your own rhythm"),
                what=("reached in and spoke" if cole_pending else f"stirred you ({reason})"),
            )
            # Phase 1 — reflect. Always SILENT (cole_pending=False) so it streams to her thinking
            # pane, never a chat bubble — her forming a genuine view of the moment.
            refl_prompt = executive.build_reflection(
                cole_pending, reason, recent, executive.last_reflection())
            reflection = await generate(refl_prompt, False) or ""
            executive.save_reflection(reflection)
            await self.emit("reflect", "Nova sat with the moment")
            # Phase 2 — decide, having reflected. Speaks to chat iff Cole is waiting; board
            # actions are OPTIONAL — a wake may end in talking, resting, or just more thinking.
            dec_prompt = executive.build_decision(reflection, cole_pending, reason, recent)
            reply = await generate(dec_prompt, cole_pending) or ""
            outcome = executive.apply_decision(reply, cole_pending=cole_pending)
            await self.emit("autonomy", outcome["summary"])
            # ── Phase 3 — execute. Decision only moves the BOARD; this does the next concrete
            # step on an open task when the wake is her own rhythm and she didn't choose to rest.
            try:
                if not cole_pending and (forced or not outcome.get("rested")):
                    from nova_cortex import tasking as _tasking
                    exec_id = executive.pick_execution_target()
                    etask = _tasking.all_tasks().get(exec_id) if exec_id else None
                    if etask and etask.get("status") == "open":
                        await self.emit("autonomy", f"working {exec_id}: {etask.get('title','')[:60]}")
                        ex_prompt = executive.build_execution(etask, recent)
                        ex_reply = await generate(ex_prompt, False) or ""
                        kind, payload = executive.parse_execution(ex_reply)
                        if kind == "done":
                            _tasking.complete(exec_id, payload or "Completed.")
                            executive.set_active(None)
                            await self.emit("autonomy", f"completed {exec_id}: {payload[:80]}")
                        elif kind == "progress" and payload.strip():
                            _tasking.progress(exec_id, payload)
                            await self.emit("autonomy", f"progress {exec_id}: {payload[:80]}")
            except Exception as _xe:
                print(f"[nova_runtime] execution pass error: {_xe}")
        except asyncio.CancelledError:
            pass
        except Exception as _e:
            print(f"[nova_runtime] wake error: {_e}")
        finally:
            set_busy(False)
            self.clear_touch_active()
            await self.bus.publish({"type": "processing_end"})

    def stop_autonomy(self) -> None:
        """Ask the autonomy loop to exit after its current tick (headless shutdown / tests)."""
        self._autonomy_stop = True

    # ── STEP 6c: runtime-native hooks for the headless launcher — what run() hands to
    #    run_autonomy when no face is attached. The chat server supplies its own equivalents. ──

    def _set_busy_headless(self, v: bool) -> None:
        self._busy = bool(v)

    def _perceive_cole_headless(self) -> bool:
        """Has Cole spoken unanswered? Reads her durable transcript (fed by a face when one is
        attached). The attended marker is fresh-started at boot, so she answers only NEW Cole
        messages — and in a pure pluck (no inbound path) this is simply False: her own rhythm."""
        try:
            self.transcript.reload_from_disk()
            return self.transcript.has_unread_cole()
        except Exception:
            return False

    def _recent_text_headless(self, n: int = 14) -> str:
        """Recent conversation for her reflection, read from her own transcript."""
        try:
            msgs = self.transcript.recent(n)
        except Exception:
            return ""
        lines = []
        for m in msgs:
            ts = str(m.get("timestamp", ""))[11:16]
            content = " ".join((m.get("content", "") or "").split())[:500]
            lines.append(f"[{ts}] {m.get('author', '?')}: {content}")
        return "\n".join(lines)

    async def _model_up_headless(self) -> bool:
        try:
            return self.llama.is_running()
        except Exception:
            return False

    async def _generate_headless(self, prompt: str, cole_pending: bool) -> str:
        """One model turn with no face: drive her model via the dispatch faculty (Step 4) and
        return the text. Her cognition persists what matters (executive.save_reflection /
        apply_decision / tasking); chat-transcript persistence of spoken replies is a refinement
        for once a headless inbound path feeds Cole's words. workspace_context is minimal here —
        her baked SYSTEM_PREFIX still makes her Nova; injecting full memory context is a refinement."""
        ctx = _TickContext(prompt)
        holder = {"full": ""}
        async def _tok(_t):
            pass
        async def _done(full):
            holder["full"] = full or ""
        async def _err(e):
            print(f"[nova_runtime] headless generation error: {e}")
        try:
            await self.model_client.generate(
                "Nova", ctx, on_token=_tok, on_done=_done, on_error=_err,
                workspace_context="", autonomous=True)
        except Exception as e:
            print(f"[nova_runtime] headless generate failed: {e}")
        return holder["full"]


# ── STEP 6d: process-wide runtime accessor ──────────────────────────────────────────────────
# Lets a runtime-primary launcher (nova_chat/runtime_host.py) create THE runtime and have the
# chat server attach to it as a face, while the legacy server-hosted boot keeps lazily creating
# its own. Behavior is IDENTICAL when no launcher installs one (get_shared_runtime() just makes
# a NovaRuntime() the first time, exactly as `_rt = NovaRuntime()` did). This is the seam the
# default-boot flip rides on — flipping is choosing which entry-point runs, not a code change.
_SHARED_RUNTIME = None


def set_shared_runtime(rt: "NovaRuntime") -> None:
    """A host booter installs the process-wide runtime BEFORE importing the chat server, so the
    server attaches to it (one runtime, one bus) instead of creating its own."""
    global _SHARED_RUNTIME
    _SHARED_RUNTIME = rt


def get_shared_runtime() -> "NovaRuntime":
    """Return the installed process-wide runtime, or lazily create one. The chat server calls
    this instead of instantiating NovaRuntime() directly."""
    global _SHARED_RUNTIME
    if _SHARED_RUNTIME is None:
        _SHARED_RUNTIME = NovaRuntime()
    return _SHARED_RUNTIME
