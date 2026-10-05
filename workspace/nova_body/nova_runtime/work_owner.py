# @nova: Serialize Nova's active work and preserve bounded input context across autonomous and conversational steps.
"""Transient body ownership; durable tasks/transcript remain their canonical stores."""
from __future__ import annotations
import asyncio
from copy import deepcopy
import json
from uuid import uuid4


class WorkLease:
    def __init__(self, coordinator, kind, focus, task):
        self.coordinator = coordinator
        self.id = uuid4().hex
        self.kind = kind
        self.focus = focus
        self.task = task
        self.depth = 1
        self.phase_outputs = []
        self.timeout = None
        self.boundary_handler = None
        self.operation = None
        self.stop_requested = False
        self._cancel_issued = False
        self.finished = asyncio.Event()

    def request_stop(self):
        """Stop this work lease, not its long-lived daemon; never own external cancellation."""
        if self.coordinator.active is not self or self.finished.is_set():
            return False
        if self.stop_requested:
            return True
        self.stop_requested = True
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

    async def __aexit__(self, *_):
        self.coordinator.release(self)


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

    async def __aexit__(self, *_):
        self.coordinator.release(self.owner)


class WorkCoordinator:
    def __init__(self):
        self.active = None
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
        self.active = WorkLease(self, str(kind), focus, task)
        self._available.clear()
        return self.active

    def lease(self, kind, *, focus=None):
        return _WaitingLease(self, kind, focus)

    def release(self, owner):
        if owner is not self.active or owner.task is not asyncio.current_task():
            raise RuntimeError("Only the owning task can release active work")
        owner.depth -= 1
        if owner.depth == 0:
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
                    ('content', 'request_id', 'reply_to', 'conversation_id')}
        accepted['role'] = 'user'
        json.dumps(accepted)  # Reject face objects/opaque handles at the body boundary.
        key = (accepted['conversation_id'], accepted['reply_to'], accepted['request_id'])
        if key != (None, None, None) and any(
            (item['conversation_id'], item['reply_to'], item['request_id']) == key for item in self._inputs):
            return True
        self._inputs.append(accepted)
        return True

    def remove_input(self, reply_to, *, conversation_id=None):
        before = len(self._inputs)
        self._inputs[:] = [item for item in self._inputs if not
                           (item.get('reply_to') == reply_to and
                            (conversation_id is None or item.get('conversation_id') == conversation_id))]
        return before - len(self._inputs)

    def context_for_input(self, max_chars=6000):
        return self.active.prompt_context(max_chars) if self.active is not None else ''

    def snapshot(self):
        owner = self.active
        return {"active": owner is not None, "id": owner.id if owner else None,
                "kind": owner.kind if owner else None, "focus": owner.focus if owner else None,
                "completed_phases": len(owner.phase_outputs) if owner else 0,
                "pending_inputs": len(self._inputs),
                "stop_requested": owner.stop_requested if owner else False}
