# @nova: Match voice turns to delivered replies and control speech eligibility, timeouts and interruption.
#   Nova Chat says it DELIVERED in reply to one of this gateway's own requests (by request_id),
#   with its audit disposition attached. Never diagnostics, never empty/suppressed/cancelled ends.
"""voice_gateway/turns.py — pending requests, end classification and speech routing.

Request lifecycle (all keyed by the request_id the gateway generated, never by speaker name):
    sent -> acknowledged (user_message echo gives the server id, reply_to)
         -> answering (message_start binds the original input; message_context binds applied follow-ups)
         -> closed by message_end, request_end, an error, or the pending timeout.
Identity (Codex review #70): a reply is ours only if its request_id is pending, its reply_to equals the
acknowledged server id, and its message_id/run_id match the message_start or validated context update.
Aligned request_ids/reply_to_ids and input_revision bind a combined reply to every applied input.
New utterances/barge-in retire earlier audio eligibility only; they never stop body work. Audited delivered segments can speak before the turn ends; uncommitted drafts remain silent.
Speech policy (first stage, agreed in the Collaboration room #55-#70):
    * speak only delivery == "delivered" (scope "mine": request_id is ours; "replies": any reply to
      a human line, still identified by reply_to);
    * never speak empty / suppressed / cancelled / error / unsolicited ends — an error end carries a
      diagnostic, and unsolicited promotions need a policy of their own (Codex #65);
    * an end without `delivery` is old schema: silent, with one local "update Nova Chat" diagnostic;
    * delivered is not approved: audit {status, reason, source} rides along to captions;
      audit_gate="delivered" (default) speaks any delivered reply with its status attached,
      audit_gate="pass_only" speaks only an explicit PASS (NOT_RUN, CONCERN, INCOMPLETE, ERROR stay silent);
    * new input preserves committed queued segments; explicit Stop/output mute flushes speech.
"""
from __future__ import annotations

import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field

from committer import commit_block
from speech import Utterance, speech_text

AUDIT_GATES = ("delivered", "pass_only")


@dataclass
class Pending:
    request_id: str
    text: str
    sent_at: float
    reply_to: str = ""
    state: str = "sent"                 # sent | acknowledged | queued | answering
    message_ids: set = field(default_factory=set)
    run_ids: dict = field(default_factory=dict)     # message_id -> run_id from its message_start
    eligible: bool = True               # only latest input may supply audio for a combined reply
    why_not: str = ""
    delayed: bool = False


class VoiceSession:
    def __init__(self, cfg, player, body, *, clock=time.monotonic, log=print):
        self.cfg, self.player, self.body, self.clock, self.log = cfg, player, body, clock, log
        self.pending: dict[str, Pending] = {}
        self._by_message: dict[str, str] = {}
        self._contexts = OrderedDict()             # message_id -> immutable run + applied-input binding
        self._segments = OrderedDict()           # committed segment cursor + unique audio unit sequence
        self._ended = deque(maxlen=512)             # duplicate terminal frames cannot speak again
        self._old_schema_warned = False
        self._retired_replies = deque(maxlen=512)
        self.output_muted = False
        if getattr(cfg, "speak_from", "final") != "final":
            body.emit("diagnostic", level="warn",
                      message="speak_from='stream' does not permit token speech; only committed delivered "
                              "segments or compatible final replies can speak (no pre-audit speech).")
        player.on_idle = self._settle

    # ── outbound ──────────────────────────────────────────────────────────────────────────────
    def sent(self, request_id: str, text: str) -> None:
        """Retire earlier audio, then register another ordered input without cancelling body work."""
        self._retire("new_request", flush=False)
        self.pending[request_id] = Pending(request_id, text, self.clock())
        self._turn(self.pending[request_id], "sent", state="waiting")
        self.body.emit("state", state="waiting", request_id=request_id)

    def _turn(self, pending, phase, **fields):
        self.body.emit("turn", phase=phase, request_id=pending.request_id,
                       elapsed_s=round(self.clock() - pending.sent_at, 3),
                       delayed=pending.delayed, **fields)

    def cancel(self, reason="voice_stopped") -> None:
        """Close this voice output immediately; never cancel another client's model request."""
        self.output_muted = True
        self._retire(reason)
        self._settle()

    def barge_in(self) -> None:
        """Cole started talking over her (full-duplex only)."""
        self._retire("barge_in", flush=False)
        self.player.pause()
        self.player.interrupt("barge_in", preserve_queue=True)

    def _retire(self, reason: str, *, flush=True) -> None:
        """Retire local audio eligibility; the worker sends Stop only for explicit shutdown."""
        for p in self.pending.values():
            if p.eligible:
                p.eligible, p.why_not = False, f"interrupted ({reason})"
                self._turn(p, "interrupted", state="waiting" if reason in {"new_request", "barge_in"} else "cancelled",
                           scope="audio" if reason in {"new_request", "barge_in"} else "request",
                           eligible=False, why=p.why_not)
        if flush:
            self.player.interrupt(reason)

    # ── inbound ───────────────────────────────────────────────────────────────────────────────
    def handle(self, ev) -> None:
        getattr(self, "_on_" + ev.kind, self._ignore)(ev)

    def _ignore(self, ev):
        pass

    def _on_ack(self, ev):
        p = self.pending.get(ev.request_id) if ev.request_id else None
        if p is not None:
            p.reply_to, p.state = ev.message_id, "acknowledged"
            self._turn(p, "acknowledged", state="waiting", reply_to=p.reply_to)

    def _on_queued(self, ev):
        # Sent only to this socket right after our message; it names no request, so it only informs.
        for p in self.pending.values():
            if p.eligible:
                p.state = "queued"
                self._turn(p, "queued", state="waiting", why=str(ev.raw.get("reason") or "Nova is busy"))
        self.body.emit("diagnostic", level="info",
                       message=str(ev.raw.get("reason") or "Nova is busy; the request is queued."))

    @staticmethod
    def _pairs(ev):
        """Validate aligned protocol identities; malformed lists never fall back to singular IDs."""
        raw = ev.raw
        if "request_ids" not in raw and "reply_to_ids" not in raw:
            return [(ev.request_id, ev.reply_to)] if ev.request_id else []
        revision = raw.get("input_revision")
        if type(revision) is not int or revision < 0:
            return None
        requests, replies = raw.get("request_ids"), raw.get("reply_to_ids")
        if not isinstance(requests, list) or not isinstance(replies, list) or len(requests) != len(replies):
            return None
        if not requests or len(requests) > 512 or any(not isinstance(value, str) or not value for value in replies):
            return None
        # Browser input may have no client request ID. Such entries remain foreign;
        # a null alias can never match this gateway's locally generated request IDs.
        named = [value for value in requests if value is not None]
        if any(not isinstance(value, str) or not value for value in named):
            return None
        if len(set(named)) != len(named) or len(set(replies)) != len(replies):
            return None
        pairs = list(zip(requests, replies))
        if ev.request_id and (ev.request_id, ev.reply_to) not in pairs:
            return None
        return pairs

    def _bind(self, ev, *, update=False):
        pairs = self._pairs(ev)
        previous = self._contexts.get(ev.message_id)
        revision = ev.raw.get("input_revision")
        valid_revision = revision is None or (type(revision) is int and revision >= 0)
        if pairs is None or not ev.message_id or not ev.run_id or not valid_revision:
            return False
        if update and type(revision) is not int:
            return False
        if previous is not None:
            if previous["run_id"] != ev.run_id:
                return False
            if pairs[:len(previous["pairs"])] != previous["pairs"]:
                return False
            old_revision = previous["revision"]
            if old_revision is not None and (revision is None or revision < old_revision):
                return False
            if pairs != previous["pairs"] and old_revision is not None and revision == old_revision:
                return False
        matched = [(self.pending[rid], reply) for rid, reply in pairs if rid in self.pending]
        if (update and previous is None and not matched) or any(not p.reply_to or p.reply_to != reply for p, reply in matched):
            return False
        revisions = OrderedDict(previous.get("revisions", {}) if previous else {})
        if revision is not None:
            revisions[revision] = list(pairs)
            while len(revisions) > 512:
                revisions.popitem(last=False)
        self._contexts[ev.message_id] = {"run_id": ev.run_id, "pairs": pairs, "revision": revision,
                                         "revisions": revisions,
                                         "modern": "request_ids" in ev.raw or "reply_to_ids" in ev.raw}
        self._contexts.move_to_end(ev.message_id)
        while len(self._contexts) > 512:
            self._contexts.popitem(last=False)
        for p, _ in matched:
            p.state = "answering"
            p.message_ids.add(ev.message_id)
            p.run_ids[ev.message_id] = ev.run_id
            self._by_message[ev.message_id] = p.request_id
            if p.eligible:
                self._turn(p, "started", state="thinking", message_id=ev.message_id, run_id=ev.run_id,
                           input_revision=revision)
                self.body.emit("state", state="thinking", request_id=p.request_id,
                               message_id=ev.message_id, run_id=ev.run_id)
        return True

    def _on_start(self, ev):
        if not self._bind(ev):
            self.body.emit("diagnostic", level="warn",
                           message="Reply start identity did not match an acknowledged voice input; no speech binding added.")

    def _on_context(self, ev):
        if not self._bind(ev, update=True):
            self.body.emit("diagnostic", level="warn",
                           message="Reply context did not match its existing run and acknowledged inputs; no speech binding added.")

    def _on_segment(self, ev):
        """Queue each committed audited segment once; final closure is a separate event."""
        if (ev.message_id, ev.run_id) in self._ended:
            return
        pairs = self._pairs(ev)
        covered = [self.pending[rid] for rid, _ in pairs or [] if rid in self.pending]
        pending = next((p for p in reversed(covered) if p.eligible), covered[-1] if covered else None)
        identity = self._identity(pending, ev, committed=True) if pending else "not one of this gateway's requests"
        index = ev.raw.get("segment_index")
        turn_id = ev.raw.get("turn_id")
        cursor = self._segments.get(ev.message_id)
        audit = ev.raw.get("audit")
        valid_audit = (isinstance(audit, dict) and audit.get("status") in
                       {"PASS", "CONCERN", "INCOMPLETE", "ERROR", "NOT_RUN"} and
                       type(audit.get("input_revision")) is int and
                       audit["input_revision"] == ev.raw.get("input_revision") and audit.get("turn_id") == turn_id)
        if (not valid_audit or pairs is None or "request_ids" not in ev.raw or identity or ev.delivery != "delivered" or
                type(index) is not int or index < 1 or not turn_id or turn_id != ev.run_id or
                (cursor and cursor["run_id"] != ev.run_id)):
            self.body.emit("diagnostic", level="warn", message="Delivered segment identity is invalid; nothing was spoken.")
            return
        if cursor is None:
            cursor = {"run_id": ev.run_id, "next": 1, "unit": 0}
            self._segments[ev.message_id] = cursor
            while len(self._segments) > 512:
                self._segments.popitem(last=False)
        if index < cursor["next"]:
            return                              # duplicate delivery must not replay audio
        if index != cursor["next"]:
            self.body.emit("diagnostic", level="warn", message="Delivered speech segment is out of order; waiting for the missing segment.")
            return
        cursor["next"] += 1
        eligible, why = self.classify(ev, pending, identity, committed=True)
        queued = self._queue_units(ev, pending.request_id, cursor, eligible)
        self.body.emit("message", phase="segment", message_id=ev.message_id, request_id=pending.request_id,
                       run_id=ev.run_id, turn_id=turn_id, segment_index=index, input_revision=ev.raw.get("input_revision"),
                       delivery=ev.delivery, audit=dict(ev.audit), eligible=eligible, queued_units=queued, why=why)
        if not queued:
            self._settle()

    def _queue_units(self, ev, request_id, cursor, eligible):
        if not eligible:
            return 0
        units = [unit.text for unit in commit_block(speech_text(ev.text), min_chars=self.cfg.min_chars,
                                                     max_buffer=self.cfg.max_buffer) if unit.text.strip()]
        queued = 0
        try:
            for text in units:
                self.player.say(Utterance(text, ev.message_id, request_id, ev.run_id,
                                          cursor["unit"], dict(ev.audit), ev.raw.get("segment_index", 0)))
                cursor["unit"] += 1
                queued += 1
        except RuntimeError as error:
            self.body.emit("diagnostic", level="warn", message=f"Speech player unavailable ({error}); remaining segment audio was not queued.")
        return queued

    def _on_end(self, ev):
        if ev.delivery is None:
            if not self._old_schema_warned:
                self._old_schema_warned = True
                self.body.emit("diagnostic", level="error",
                               message="Nova Chat sent a reply end without delivery metadata (old server). "
                                       "Nothing from it is spoken; restart or update Nova Chat.")
            return
        if (ev.message_id, ev.run_id) in self._ended:
            return
        count = ev.raw.get("segment_count", 0)
        if type(count) is not int or count < 0:
            self.body.emit("diagnostic", level="warn", message="Reply end has an invalid segment count; no speech or closure accepted.")
            return
        pairs = self._pairs(ev)
        covered = [self.pending[rid] for rid, _ in pairs or [] if rid in self.pending]
        pending = next((p for p in reversed(covered) if p.eligible), covered[-1] if covered else None)
        request_id = pending.request_id if pending is not None else ev.request_id
        identity = self._identity(pending, ev) if pending is not None else "not one of this gateway's requests"
        modern = "request_ids" in ev.raw or "reply_to_ids" in ev.raw
        if pairs is None:
            eligible, why = False, "malformed combined reply identity"
        else:
            eligible, why = self.classify(ev, pending, identity)
        # Never let a forged/mismatched combined terminal consume legitimate pending inputs.
        prior = self._contexts.get(ev.message_id)
        legacy = not modern and not (prior and prior["modern"])
        if legacy or (pending is not None and not identity):
            for p in covered:
                self._close(p.request_id)
            if ev.message_id and ev.run_id and (not identity or eligible):
                self._ended.append((ev.message_id, ev.run_id))
                self._contexts.pop(ev.message_id, None)
        segmented = ev.raw.get("segment_count", 0)
        segmented = type(segmented) is int and segmented > 0 or ev.message_id in self._segments
        units = []
        if segmented:
            why = "Turn complete; delivered segments are not replayed from the aggregate."
            seen = self._segments.get(ev.message_id, {}).get("next", 1) - 1
            if not identity and count != seen:
                self.body.emit("diagnostic", level="warn", message=f"Turn ended with {count} delivered segments; this voice connection received {seen}. Aggregate audio will not be replayed.")
        if eligible and not segmented:
            units = [u.text for u in commit_block(speech_text(ev.text), min_chars=self.cfg.min_chars,
                                                  max_buffer=self.cfg.max_buffer)]
            units = [t for t in units if t.strip()]
            if not units:
                why = "nothing speakable after removing code, markers and links"
        # Policy and queueing only; whether audio actually played is in the speech events.
        self.body.emit("message", phase="end", message_id=ev.message_id, request_id=request_id,
                       run_id=ev.run_id, delivery=ev.delivery, audit=dict(ev.audit), eligible=eligible,
                       queued_units=len(units), why=why,
                       segment_count=ev.raw.get("segment_count", 0),
                       elapsed_s=round(self.clock() - pending.sent_at, 3) if pending else None)
        if pending is not None and not units and not segmented:
            self.body.emit("diagnostic", level="warn", request_id=request_id,
                           message=f"Nova's reply was not spoken: {why}.")
        if ev.delivery == "error":
            self.log(f"[voice_gateway] Nova Chat error end (never spoken): {ev.text[:300]}")
        try:
            for i, text in enumerate(units):
                self.player.say(Utterance(text, ev.message_id, request_id, ev.run_id, i, dict(ev.audit)))
        except RuntimeError as error:            # player closed during shutdown: drop, don't crash the link
            self.body.emit("diagnostic", level="warn",
                           message=f"Speech player unavailable ({error}); {len(units)} unit(s) not queued.")
            units = []
        if not units:
            self._settle()

    def _on_request_end(self, ev):
        if ev.request_id in self.pending:
            self._close(ev.request_id)
            self.body.emit("diagnostic", level="warn", request_id=ev.request_id,
                           message=f"Voice request ended without a spoken reply ({ev.delivery}).")
            self.body.emit("message", phase="dropped", request_id=ev.request_id, delivery=ev.delivery,
                           eligible=False, queued_units=0, why=f"request ended before a reply ({ev.delivery})")
            self._settle()

    def _on_error(self, ev):
        request_id = ev.request_id or self._by_message.get(ev.message_id, "")
        self.body.emit("diagnostic", level="error", message=f"Nova Chat error: {ev.text[:300]}")
        if request_id in self.pending:
            self._close(request_id)
            self._settle()

    def _on_stopped(self, ev):
        if ev.request_id:
            pending = self.pending.get(ev.request_id)
            if ev.raw.get("matched") is True and pending is not None:
                pending.eligible, pending.why_not = False, "interrupted (request stopped)"
                self._turn(pending, "interrupted", state="cancelled", eligible=False, why=pending.why_not)
                self._close(ev.request_id)
                current = getattr(self.player, "current", None)
                if current is not None and current.request_id == ev.request_id:
                    self.player.interrupt("request_stopped")
                self._settle()
            return                         # an old scoped acknowledgement never stops a new turn
        self._retire("stopped")
        self._settle()

    # ── policy ────────────────────────────────────────────────────────────────────────────────
    def _identity(self, p, ev, *, committed=False) -> str:
        """'' when the end provably answers request p; otherwise why not."""
        if not p.reply_to:
            return "request never acknowledged (no user_message echo)"
        pairs = self._pairs(ev)
        if pairs is None or (p.request_id, p.reply_to) not in pairs:
            return "reply_to does not match the acknowledged request"
        binding = self._contexts.get(ev.message_id)
        modern = "request_ids" in ev.raw or "reply_to_ids" in ev.raw
        if binding is not None and binding["modern"] and not modern:
            return "combined reply omitted its applied context identities"
        if modern:
            revision = ev.raw.get("input_revision")
            matched_revision = binding and (binding.get("revisions", {}).get(revision) == pairs if committed
                                               else binding["pairs"] == pairs and binding["revision"] == revision)
            if not matched_revision:
                return "combined inputs do not match their applied context revision"
        if ev.message_id not in p.message_ids:
            return "no matching message_start for this message"
        if not ev.run_id or p.run_ids.get(ev.message_id) != ev.run_id:
            return "run_id does not match its message_start"
        return ""

    def classify(self, ev, pending=None, identity: str = "not one of this gateway's requests", *, committed=False):
        """(speak?, why) for one message_end. The only place speech policy lives."""
        scope = getattr(self.cfg, "speak_scope", "mine")
        if self.output_muted:
            return False, "voice output is muted"
        if not ev.text.strip():
            return False, f"nothing to say (delivery={ev.delivery})"
        if ev.delivery == "unsolicited":
            return False, "unsolicited message (needs its own policy; never spoken in the first stage)"
        if ev.delivery != "delivered":
            return False, f"delivery={ev.delivery} is never spoken"
        if pending is not None:
            if not pending.eligible and not (committed and pending.why_not in {
                    "interrupted (new_request)", "interrupted (barge_in)"}):
                return False, pending.why_not
            if identity:
                return False, identity
        elif scope == "mine":
            return False, "not a reply to a voice request"
        elif scope != "replies" or not ev.reply_to or ev.reply_to in self._retired_reply_ids():
            return False, "not a reply to a human line"
        status = ev.audit.get("status", "NOT_RUN")
        gate = getattr(self.cfg, "audit_gate", "delivered")
        if gate not in AUDIT_GATES:
            return False, f"unknown audit_gate {gate!r}; speaking nothing"
        if gate == "pass_only" and status != "PASS":
            return False, f"audit {status} withheld by audit_gate=pass_only"
        return True, f"delivered (audit {status})"

    def _retired_reply_ids(self) -> set:
        return set(self._retired_replies) | {p.reply_to for p in self.pending.values() if not p.eligible and p.reply_to}

    # ── housekeeping ──────────────────────────────────────────────────────────────────────────
    def sweep(self) -> list:
        """Expire unacknowledged/retired requests; retain the current accepted slow reply.

        A slow model is not a cancelled turn. Keep its exact correlation while this socket
        lives, announce the delay once, and let an explicit stop/new utterance retire it.
        Inputs bound to an open response remain available for that response's committed segments.
        Terminal closure removes them; unbound retired requests still expire.
        """
        limit = float(getattr(self.cfg, "request_timeout_s", 300))
        stale = []
        for rid, pending in list(self.pending.items()):
            if self.clock() - pending.sent_at <= limit:
                continue
            bound = any(mid in self._contexts and self._contexts[mid]["run_id"] == pending.run_ids.get(mid)
                        for mid in pending.message_ids)
            if pending.reply_to and (pending.eligible or bound):
                if not pending.delayed:
                    pending.delayed = True
                    self._turn(pending, "delayed", state="waiting",
                               why="Nova has accepted this request; waiting for the delayed reply")
                    self.body.emit("diagnostic", level="warn", request_id=rid,
                                   message=f"Nova's voice reply is taking longer than {int(limit)} s. "
                                           "Its open reply binding is retained; speech still follows delivery, mute and audit policy.")
                continue
            stale.append(rid)
            self._turn(pending, "expired", state="idle", eligible=False,
                       why="No acknowledgement before timeout" if pending.eligible else pending.why_not)
            self._close(rid)
            if pending.eligible:
                self.body.emit("diagnostic", level="warn", request_id=rid,
                               message=f"Voice request was not acknowledged within {int(limit)} s; it was dropped.")
        if stale:
            self._settle()
        return stale

    def _close(self, request_id):
        p = self.pending.pop(request_id, None)
        if p is not None:
            if not p.eligible and p.reply_to:
                self._retired_replies.append(p.reply_to)
            for mid in p.message_ids:
                if self._by_message.get(mid) == request_id:
                    self._by_message.pop(mid, None)

    def _settle(self):
        if self.player.active():
            return
        eligible = [p for p in self.pending.values() if p.eligible]
        if eligible:
            self.body.emit("state", state="thinking" if any(p.state == "answering" and not p.delayed for p in eligible)
                           else "waiting")
        else:
            self.body.emit("state", state="idle")
