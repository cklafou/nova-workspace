# @nova: Bind response events to their request, run and delivery outcome without inferring audit approval.
# Last updated: 2026-10-05 21:27:11
from __future__ import annotations
import re
from copy import deepcopy


def normalize_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else None


class ResponseEvents:
    def __init__(self, *, author, message_id, run_id, reply_to=None, request_id=None, register="text", conversation_id=None):
        self.context = dict(author=author, id=message_id, run_id=run_id,
                            reply_to=reply_to, request_id=normalize_request_id(request_id), register=register, conversation_id=conversation_id)
        self.audit = {"status": "NOT_RUN", "reason": "No audit disposition supplied for this candidate.", "source": "none"}
        self.closed = set()
        self.context.update(request_ids=[], reply_to_ids=[], input_revision=0)
        self.add_input(request_id, reply_to)
        self.context["turn_id"] = run_id
        self.revisions = {0: deepcopy(self.context)}
        self.segments = []

    def add_input(self, request_id, reply_to):
        """Keep aligned input aliases so a continued reply covers every accepted input."""
        pair = (normalize_request_id(request_id), reply_to)
        pairs = list(zip(self.context["request_ids"], self.context["reply_to_ids"]))
        if pair != (None, None) and pair not in pairs:
            self.context["request_ids"].append(pair[0])
            self.context["reply_to_ids"].append(pair[1])

    def apply_inputs(self, entries, revision):
        for entry in entries:
            self.add_input(entry.get("request_id"), entry.get("reply_to"))
        self.context["input_revision"] = revision
        self.revisions[revision] = deepcopy(self.context)
        self.audit = {"status": "NOT_RUN", "reason": "New input requires a current candidate audit.", "source": "none"}

    async def on_audit(self, value):
        if not isinstance(value, dict):
            value = {}
        status = value.get("status")
        if status not in {"PASS", "CONCERN", "INCOMPLETE", "ERROR", "NOT_RUN"}:
            self.audit = {"status": "INCOMPLETE", "reason": "Invalid audit disposition.", "source": "none"}
        else:
            self.audit = {"status": status, "reason": str(value.get("reason") or "")[:2000],
                          "source": str(value.get("source") or "inline")[:80]}
            if "input_revision" in value:
                revision = value["input_revision"]
                if type(revision) is not int or revision != self.context["input_revision"]:
                    self.audit = {"status": "INCOMPLETE", "source": "none",
                                  "reason": "Audit input revision does not match the current candidate."}
                else:
                    self.audit["input_revision"] = revision
                    self.audit["turn_id"] = self.context["run_id"]

    @property
    def delivered_content(self):
        return "\n\n".join(part["content"] for part in self.segments)

    def prepare_segment(self, text, metadata):
        """Bind one committed step to the immutable inputs/evidence it actually used."""
        if self.context["id"] in self.closed:
            raise ValueError("Cannot append a segment to closed work")
        if not isinstance(text, str) or not text.strip() or not isinstance(metadata, dict):
            raise ValueError("A segment requires completed non-empty text and metadata")
        index, revision = metadata.get("segment_index"), metadata.get("input_revision")
        if type(index) is not int or index != len(self.segments) + 1:
            raise ValueError("Segment index must advance exactly once")
        if type(revision) is not int or revision not in self.revisions:
            raise ValueError("Segment references an unknown input revision")
        if metadata.get("turn_id") != self.context["run_id"]:
            raise ValueError("Segment belongs to another work run")
        audit = deepcopy(metadata.get("audit"))
        if not isinstance(audit, dict) or audit.get("status") not in {
                "PASS", "CONCERN", "INCOMPLETE", "ERROR", "NOT_RUN"}:
            raise ValueError("Segment requires an explicit audit disposition")
        if audit.get("input_revision") != revision or audit.get("turn_id") != metadata["turn_id"]:
            raise ValueError("Segment audit does not match its work/input revision")
        event = {**deepcopy(self.revisions[revision]), "type": "message_segment",
                 "segment_index": index, "content": text, "delivery": "delivered", "audit": audit}
        return event

    def commit_segment(self, event):
        if event.get("segment_index") != len(self.segments) + 1 or self.context["id"] in self.closed:
            raise ValueError("Segment commitment must follow prepared order")
        self.segments.append(deepcopy(event))
        return event

    def segment(self, text, metadata):
        """Convenience for in-memory sinks; persistent adapters prepare then commit after writing."""
        return self.commit_segment(self.prepare_segment(text, metadata))

    def event(self, kind, **fields):
        event = {**self.context, "type": kind, **fields}
        event["request_ids"] = list(self.context["request_ids"])
        event["reply_to_ids"] = list(self.context["reply_to_ids"])
        if kind == "message_end":
            identity = event["id"]
            if identity in self.closed:
                return None
            self.closed.add(identity)
            delivery = event.get("delivery", "empty")
            event["audit"] = dict(self.audit)
            event["segment_count"] = len(self.segments)
            if delivery == "unsolicited":
                event.update(reply_to=None, request_id=None, request_ids=[], reply_to_ids=[])
                event["audit"] = {"status": "NOT_RUN", "reason": "Extracted autonomous message is not the audited full candidate.", "source": "none"}
            elif delivery != "delivered":
                event["audit"] = {"status": "NOT_RUN", "reason": "No normal final candidate was delivered.", "source": "none"}
        return event
