# Last updated: 2026-10-06 03:45:19
# @nova: Own ordered active-turn continuation and final-delivery admission independently of any chat face.
"""One event-loop-owned turn; input appends at natural model/tool boundaries.

This is transient execution state, not a second task board or personal memory store.
Only explicit Stop cancels work. Faces retain their durable transcript separately.
"""
import asyncio
from copy import deepcopy
import inspect
import hashlib
import json
from uuid import uuid4

ANCHOR = "_nova_request_anchor"
RECEIPT_ANCHOR = "_nova_receipt_anchor"


def cancellation_requested(task=None):
    """Support Python 3.10 tasks as well as the 3.11+ cancellation counter."""
    task = task or asyncio.current_task()
    if task is None:
        return False
    counter = getattr(task, "cancelling", None)
    if callable(counter):
        return bool(counter())
    return bool(task.cancelled() or getattr(task, "_must_cancel", False))


def observer_cancel_is_external(task=None):
    task = task or asyncio.current_task()
    # Older Python cannot reliably distinguish an observer raising CancelledError
    # from a real delivered task cancellation. Preserve Stop rather than swallowing it.
    return not callable(getattr(task, "cancelling", None)) or cancellation_requested(task)


def provider_messages(messages):
    """Remove internal ownership/anchor metadata before calling an external provider."""
    return [{k: v for k, v in message.items() if not k.startswith("_nova_")}
            for message in messages]


def completed_action_message(tool, args, observation, *, operation_id, run_id, status, ok, exit_code):
    """Small durable-in-turn action fact; raw observation is still separately retained.

    Digests identify the complete arguments/observation, not evidence of success.
    The summary never invents a successful result from a failed/unknown attempt.
    """
    arguments = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    facts = {"tool": str(tool)[:120], "operation_id": str(operation_id or "")[:128],
             "run_id": str(run_id or "")[:128], "status": str(status)[:32],
             "ok": ok if isinstance(ok, bool) else None,
             "exit_code": exit_code if isinstance(exit_code, int) else None,
             "args_preview": arguments[:240], "args_preview_truncated": len(arguments) > 240,
             "args_sha256": hashlib.sha256(arguments.encode("utf-8")).hexdigest(),
             "observation_sha256": hashlib.sha256(str(observation).encode("utf-8")).hexdigest()}
    return {"role": "user", RECEIPT_ANCHOR: True, "content":
        "[System Completed Tool Attempt]\n" + json.dumps(facts, ensure_ascii=False) +
        "\nThis attempt already ran. Its full observation may be shortened or omitted by context fitting; "
        "missing detail does not mean the action did not run. Repeat only if the task requires it, "
        "not merely to replace a clipped receipt."}


class ActiveTurn:
    def __init__(self, *, turn_id=None, on_apply=None):
        self.turn_id = str(turn_id or uuid4().hex)
        self.revision = 0
        self.applied_revision = 0
        self.on_apply = on_apply
        self.last_observer_error = None
        self._pending = []
        self._closed = False

    @property
    def pending(self):
        return bool(self._pending)

    @property
    def can_accept(self):
        return not self._closed

    def has_pending(self):
        return self.pending

    def pending_inputs(self):
        """Inspect queued permissions without consuming, acknowledging or revising input.

        Mutable message data is copied. The opaque face-owner handle keeps its
        identity, as in push/consume; it is not message data and may not be copied.
        """
        return [{key: value if key == "owner" else deepcopy(value)
                 for key, value in entry.items()} for entry in self._pending]

    def push(self, entries):
        """Atomically accept an ordered batch; never cancel a running model/tool."""
        if self._closed:
            return False
        prepared = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("role", "user") != "user":
                raise ValueError("Continuation entries must be user messages")
            content = entry.get("content")
            if not isinstance(content, (str, list)) or not content:
                raise ValueError("Continuation entries need nonempty text or content parts")
            # Preserve opaque face-owner identity while isolating mutable message data.
            prepared.append({**entry, "role": "user", "content": deepcopy(content)})
        if not prepared:
            return False
        self._pending.extend(prepared)
        self.revision += 1
        return True

    async def consume(self):
        """Claim before awaiting the face observer; input during it remains pending."""
        task = asyncio.current_task()
        if cancellation_requested(task):
            raise asyncio.CancelledError
        batch, revision = self._pending, self.revision
        self._pending = []
        if not batch:
            return [], self.applied_revision
        self.applied_revision = revision
        if self.on_apply is not None:
            # Face detachment must not erase accepted input or stop Nova's body.
            # Observers receive their own content copy, plus the opaque owner handle.
            observed = [{**entry, "content": deepcopy(entry["content"])} for entry in batch]
            try:
                result = self.on_apply(observed, revision)
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                if observer_cancel_is_external(task):
                    raise  # explicit Stop still owns cancellation
                self.last_observer_error = "CancelledError"
            except Exception as exc:
                self.last_observer_error = type(exc).__name__
        if cancellation_requested(task):
            raise asyncio.CancelledError  # an observer cannot swallow explicit Stop
        return batch, revision

    def try_seal(self):
        """Final commit admission: no await may separate this from the final sink."""
        if self.pending:
            return False
        if self._closed:
            return False
        self._closed = True
        return True

    def close(self):
        """Stop admission and return any unconsumed entries for terminal reporting."""
        self._closed = True
        pending, self._pending = self._pending, []
        return pending


class ConversationTurns:
    """Body-owned active turn registry; independent conversations never share input."""
    def __init__(self):
        self._active = {}

    def begin(self, conversation_id, *, turn_id=None, on_apply=None):
        previous = self._active.get(conversation_id)
        if previous is not None and previous.can_accept:
            raise RuntimeError("Conversation already has an active turn")
        turn = ActiveTurn(turn_id=turn_id, on_apply=on_apply)
        self._active[conversation_id] = turn
        return turn

    def get(self, conversation_id):
        return self._active.get(conversation_id)

    def submit(self, conversation_id, entries):
        turn = self.get(conversation_id)
        return bool(turn is not None and turn.push(entries))

    def end(self, conversation_id, turn=None):
        active = self.get(conversation_id)
        if active is None or (turn is not None and active is not turn):
            return []
        del self._active[conversation_id]
        return active.close()
