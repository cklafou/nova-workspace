# Last updated: 2026-10-06 03:19:20
# @nova: Serialize Nova's active work and preserve bounded input context across autonomous and conversational steps.
"""Body work ownership with optional atomic restart checkpoints and no uncertain replay."""
from __future__ import annotations
import asyncio
from copy import deepcopy
import json
from uuid import uuid4
from contextvars import ContextVar
from nova_runtime.recovery import RecoveryStore, RecoveryWriteError, input_key

_current_owner = ContextVar("nova_work_owner", default=None)

def current_work_owner():
    owner = _current_owner.get()
    return owner if owner is not None and owner.task is asyncio.current_task() else None



class WorkLease:
    def __init__(self, coordinator, kind, focus, task, restored=None):
        self.coordinator = coordinator
        self.id = uuid4().hex
        self.requested_kind = kind
        self.kind = (restored or {}).get('kind', kind)
        self.focus = focus
        self.task = task
        self.depth = 1
        self.phase_outputs = []
        self.timeout = None
        self.boundary_handler = None
        self.operation = None
        self.stop_requested = False
        self._cancel_issued = False
        self.stop_persistence_error = None
        self.finished = asyncio.Event()
        self._context_token = None
        self._bound_inputs = []
        self.recovered = bool(restored)
        self._made_progress = False
        if restored:
            self.id = restored['id']
            self.focus = restored.get('focus') or focus
            self.phase_outputs = deepcopy(restored.get('phase_outputs', []))
        self.goal = (restored or {}).get('goal', '')
        self._restored = deepcopy(restored)

    def _snapshot(self):
        store = self.coordinator.store
        existing = (self._restored if self._context_token is None and self._restored else
                    (store.data.get('active') if store else None)) or {}
        value = deepcopy(existing) if existing.get('id') == self.id else {}
        value.update(id=self.id, kind=self.kind, focus=self.focus, state='active',
                     recovered=self.recovered, phase_outputs=deepcopy(self.phase_outputs),
                     stop_requested=self.stop_requested)
        if self.goal:
            value['goal'] = self.goal
        value.setdefault('goal', '')
        value.setdefault('input_keys', [])
        value.setdefault('attempts', {})
        value.setdefault('segments', {})
        value.setdefault('generations', {})
        return value

    def _persist(self):
        if self.coordinator.store:
            self.coordinator.store.sync(self._snapshot())

    def bind_inputs(self, entries_or_keys):
        keys = []
        for entry in entries_or_keys:
            keys.append(self.coordinator.receive_input(entry) if isinstance(entry, dict) else str(entry))
        self._bound_inputs = list(dict.fromkeys(keys))
        if self.coordinator.store:
            self.coordinator.store.bind(self.id, self._bound_inputs)
            self.goal = self.coordinator.store.data['active'].get('goal', '')
        return self._bound_inputs

    async def checkpoint(self, event):
        if self.coordinator.active is not self or asyncio.current_task() is not self.task:
            raise RuntimeError('Checkpoint requires active owner')
        self._made_progress = True
        if event.get('type') == 'inputs_applied':
            keys = [str(entry['input_key']) if entry.get('input_key') else self.coordinator.receive_input(entry)
                    for entry in event.get('entries', [])]
            self._bound_inputs = list(dict.fromkeys(self._bound_inputs + keys))
            if self.coordinator.store:
                self.coordinator.store.bind(self.id, self._bound_inputs)
        if self.coordinator.store:
            return self.coordinator.store.event(self.id, event, self._bound_inputs)
        return None

    async def run_action(self, name, args, callback):
        """Apply runtime board mutations through the same persisted attempt barrier."""
        operation_id = uuid4().hex
        permission = await self.checkpoint({'type':'tool_started', 'tool':'runtime.'+name,
            'args':args, 'operation_id':operation_id})
        if isinstance(permission, dict) and permission.get('allow') is False:
            self.mark_interrupted(permission['reason'])
            raise RuntimeError(permission['reason'])
        try:
            result = await callback()
        except BaseException:
            # No completion is the honest receipt while an effect may still have happened.
            raise
        await self.checkpoint({'type':'tool_completed', 'operation_id':operation_id,
            'outcome':{'ok':True, 'status':'completed', 'text':str(result)}})
        return result

    def mark_interrupted(self, reason):
        if self.coordinator.store:
            self._persist()
            self.coordinator.store.update(lambda data: data['active'].update(interrupted=True, interruption_reason=str(reason)[:1000]))

    def mark_stopped(self):
        self.stop_requested = True
        try:
            self._persist()
            if self.coordinator.store:
                self.coordinator.store.update(lambda data: data['active'].update(state='stopping'))
        except RecoveryWriteError as exc:
            # Explicit Stop still cancels the real operation. Report the lost durability;
            # never turn a full disk into permission for work to continue.
            self.stop_persistence_error = str(exc)
            self.coordinator.persistence_error = str(exc)
            return False
        return True

    def request_stop(self):
        """Stop this work lease, not its long-lived daemon; never own external cancellation."""
        if self.coordinator.active is not self or self.finished.is_set():
            return False
        if self.stop_requested:
            return True
        self.mark_stopped()
        if not self._cancel_issued and not self.task.done() and self.task.cancelling() == 0:
            self._cancel_issued = True
            self.task.cancel()
        return True

    def absorb_requested_stop(self):
        if (self.stop_requested and self._cancel_issued and
                asyncio.current_task() is self.task and self.task.cancelling() == 1):
            self.task.uncancel()
            self._cancel_issued = False
            return True
        return False

    @property
    def pending(self):
        return bool(self.coordinator._inputs)

    def take_inputs(self):
        if asyncio.current_task() is not self.task:
            raise RuntimeError("Only the active work owner may consume input")
        entries, self.coordinator._inputs = self.coordinator._inputs, []
        return entries

    def record_phase(self, phase, text, operation_id=None):
        self.phase_outputs.append({"phase": str(phase), "text": str(text or ""),
                                   "operation_id": operation_id})
        self._made_progress = True
        self._persist()

    async def on_boundary(self, facts):
        """Attend at a natural completed-call/tool boundary; never control inference."""
        if self.coordinator.active is not self or asyncio.current_task() is not self.task:
            raise RuntimeError("Boundary attention requires the active owning task")
        if facts:
            frozen = deepcopy(facts)
            self.record_phase("boundary:" + str(frozen.get("stage", "unknown")),
                              json.dumps(frozen, ensure_ascii=False))
        if self.boundary_handler is None:
            return []
        return await self.boundary_handler(facts)

    def prompt_context(self, max_chars=6000):
        """Working summaries are context, not a substitute for verified tool receipts."""
        header = (f"[ONGOING BODY WORK] work_id={self.id}; kind={self.kind}; focus={self.focus or 'not selected'}\n"
                  "Human input joins this ongoing work. Answering does not complete or erase its original goal. "
                  "Preserve completed actions; change focus only deliberately. The following are completed phase "
                  "outputs, not a reconstruction of private live reasoning or proof that an action succeeded.\n")
        pieces = [header]
        saved = self._snapshot()
        if saved.get('goal'):
            pieces.append('Original goal: ' + str(saved['goal'])[:2000] + '\n')
        if self.recovered:
            pieces.append('[RESTART RECOVERY] Continue preserved work; do not repeat delivered segments or completed actions. '
                'Started actions lacking confirmed results are uncertain, never assumed failed or safe to retry. '
                'Inspect receipts/environment before any deliberate reconciliation.\n')
            pieces.append('To reconcile after inspection, use body control '
                '{"tool":"reconcile_attempt","args":{"operation_id":"saved attempt ID",'
                '"outcome":"verified_completed|verified_not_applied|uncertain",'
                '"evidence":"what the observation establishes",'
                '"verification_operation_ids":["completed read-only receipt ID"]}}. '
                'Do not infer not-applied merely from missing logs or an error. Uncertain keeps the hold.\n')
            attempts = list(saved.get('attempts', {}).values())
            for attempt in attempts[-8:]:
                pieces.append('Saved attempt: ' + json.dumps(attempt, ensure_ascii=False)[:700] + '\n')
            segments = list(saved.get('segments', {}).values())
            for segment in segments[-4:]:
                pieces.append('Saved output (' + str(segment.get('state')) + '): ' + str(segment.get('text',''))[:500] + '\n')

        selected = self.phase_outputs[-3:]
        if len(self.phase_outputs) > len(selected):
            pieces.append(f"[{len(self.phase_outputs)-len(selected)} earlier completed phase outputs omitted here]\n")
        allowance = max(0, int(max_chars) - sum(map(len, pieces)) - 40)
        each = allowance // max(1, len(selected))
        for phase in selected:
            text = phase['text']
            if len(text) > max(0, each-100):
                text = text[:max(0, each-140)] + "\n[phase output shortened for context; complete output retained by active owner]"
            pieces.append(f"Phase {phase['phase']} (operation {phase['operation_id'] or 'unknown'}):\n{text}\n")
        result = ''.join(pieces) + "[END ONGOING BODY WORK]"
        if len(result) > max_chars:
            marker = "\n[ongoing-work context shortened]"
            result = result[:max(0, max_chars-len(marker))] + marker[:max_chars]
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.coordinator.release(self, error=exc_type is not None)


class _WaitingLease:
    def __init__(self, coordinator, kind, focus):
        self.coordinator, self.kind, self.focus = coordinator, kind, focus
        self.owner = None

    async def __aenter__(self):
        while self.owner is None:
            self.owner = self.coordinator.try_claim(self.kind, focus=self.focus)
            if self.owner is None:
                await self.coordinator._available.wait()
        return self.owner

    async def __aexit__(self, exc_type, exc, tb):
        self.coordinator.release(self.owner, error=exc_type is not None)


class WorkCoordinator:
    def __init__(self, checkpoint_path=None):
        self.store = RecoveryStore(checkpoint_path) if checkpoint_path is not None else None
        self.active = None
        self.persistence_error = None
        self._inputs = []
        self._available = asyncio.Event()
        self._available.set()

    def try_claim(self, kind, *, focus=None):
        """Synchronous admission before any await; only the same task is reentrant."""
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Work ownership requires an asyncio task")
        if self.active is not None:
            if self.active.task is task:
                self.active.depth += 1
                return self.active
            return None
        restored = self.store.resumable() if self.store else None
        owner = WorkLease(self, str(kind), focus, task, restored)
        if self.store:
            self.store.start(owner._snapshot())
        self.active = owner
        owner._context_token = _current_owner.set(owner)
        self._available.clear()
        return self.active

    def lease(self, kind, *, focus=None):
        return _WaitingLease(self, kind, focus)

    def release(self, owner, *, error=False):
        if owner is not self.active or owner.task is not asyncio.current_task():
            raise RuntimeError("Only the owning task can release active work")
        owner.depth -= 1
        if owner.depth == 0:
            try:
                if self.store:
                    saved = owner._snapshot()
                    incomplete = error or saved.get('interrupted') or (owner.recovered and not owner._made_progress)
                    state = ('stopped' if owner.stop_requested else 'paused' if owner.recovered and owner.kind == 'autonomy' and owner.requested_kind == 'conversation'
                             else 'interrupted' if incomplete else 'completed')
                    self.store.finish(saved, state)
            except RecoveryWriteError as exc:
                self.persistence_error = str(exc)
                raise
            finally:
                try:
                    if owner._context_token is not None:
                        _current_owner.reset(owner._context_token)
                finally:
                    self.active = None
                    owner.finished.set()
                    self._available.set()
        # Accepted input is retained for the next owner or explicit cancellation.

    def submit_input(self, entry):
        if self.active is None or self.active.kind != 'autonomy':
            return False
        if not isinstance(entry, dict) or entry.get('role', 'user') != 'user':
            raise ValueError("Body inputs must be user perceptions")
        content = entry.get('content')
        if not isinstance(content, (str, list)) or not content:
            raise ValueError("Body inputs need nonempty content")
        accepted = {key: deepcopy(entry.get(key)) for key in
                    ('content', 'request_id', 'reply_to', 'conversation_id', 'register', 'images', 'directed_at', 'input_key', 'author')}
        accepted['role'] = 'user'
        json.dumps(accepted)  # Reject face objects/opaque handles at the body boundary.
        key = (accepted['conversation_id'], accepted['reply_to'], accepted['request_id'])
        if key != (None, None, None) and any(
            (item['conversation_id'], item['reply_to'], item['request_id']) == key for item in self._inputs):
            return True
        accepted["input_key"] = self.receive_input(accepted)
        self._inputs.append(accepted)
        return True

    def remove_input(self, reply_to, *, conversation_id=None):
        before = len(self._inputs)
        self._inputs[:] = [item for item in self._inputs if not
                           (item.get('reply_to') == reply_to and
                            (conversation_id is None or item.get('conversation_id') == conversation_id))]
        return before - len(self._inputs)

    def receive_input(self, entry):
        return self.store.receive(entry) if self.store else input_key(entry)

    def recovery_inputs(self):
        return self.store.pending_inputs() if self.store else []

    def cancel_input(self, key_or_reply, conversation_id=None):
        return self.store.cancel_input(key_or_reply, conversation_id) if self.store else 0

    @property
    def recovery_pending(self):
        return bool(self.store and self.store.resumable())

    @property
    def recovery_blocked(self):
        return bool(self.store and (self.store.data.get('active') or {}).get('needs_reconciliation'))

    def confirm_publication(self, turn_id, segment_index, text):
        return self.store.confirm_publication(turn_id, segment_index, text, finalize=self.active is None) if self.store else False

    def resolve_attempt(self, operation_id, outcome, evidence):
        if not self.store:
            raise RuntimeError('No recovery store')
        self.store.resolve_attempt(operation_id, outcome, evidence)

    def context_for_input(self, max_chars=6000):
        return self.active.prompt_context(max_chars) if self.active is not None else ''

    def snapshot(self):
        owner = self.active
        return {"active": owner is not None, "id": owner.id if owner else None,
                "kind": owner.kind if owner else None, "focus": owner.focus if owner else None,
                "completed_phases": len(owner.phase_outputs) if owner else 0,
                "pending_inputs": len(self._inputs),
                "stop_requested": owner.stop_requested if owner else False,
                "persistence_error": self.persistence_error,
                "recovery_pending": self.recovery_pending,
                "recovery_blocked": self.recovery_blocked,
                "durable_pending_inputs": len(self.recovery_inputs()),
                "uncertain_attempts": sum(a.get('state') in ('started', 'uncertain') for a in
                    (((self.store.data.get('active') or {}).get('attempts', {}).values()) if self.store else []))}
