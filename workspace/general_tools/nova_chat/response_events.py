# @nova: Bind response events to their request, run and delivery outcome without inferring audit approval.
from __future__ import annotations
import re


def normalize_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else None


class ResponseEvents:
    def __init__(self, *, author, message_id, run_id, reply_to=None, request_id=None, register="text"):
        self.context = dict(author=author, id=message_id, run_id=run_id,
                            reply_to=reply_to, request_id=normalize_request_id(request_id), register=register)
        self.audit = {"status": "NOT_RUN", "reason": "No audit disposition supplied for this candidate.", "source": "none"}
        self.closed = set()

    async def on_audit(self, value):
        if not isinstance(value, dict):
            value = {}
        status = value.get("status")
        if status not in {"PASS", "CONCERN", "INCOMPLETE", "ERROR", "NOT_RUN"}:
            self.audit = {"status": "INCOMPLETE", "reason": "Invalid audit disposition.", "source": "none"}
        else:
            self.audit = {"status": status, "reason": str(value.get("reason") or "")[:2000],
                          "source": str(value.get("source") or "inline")[:80]}

    def event(self, kind, **fields):
        event = {**self.context, "type": kind, **fields}
        if kind == "message_end":
            identity = event["id"]
            if identity in self.closed:
                return None
            self.closed.add(identity)
            delivery = event.get("delivery", "empty")
            event["audit"] = dict(self.audit)
            if delivery == "unsolicited":
                event.update(reply_to=None, request_id=None)
                event["audit"] = {"status": "NOT_RUN", "reason": "Extracted autonomous message is not the audited full candidate.", "source": "none"}
            elif delivery != "delivered":
                event["audit"] = {"status": "NOT_RUN", "reason": "No normal final candidate was delivered.", "source": "none"}
        return event
