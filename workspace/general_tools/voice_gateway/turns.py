# Last updated: 2026-10-05 18:36:12
# @nova: Match voice turns to delivered replies and control speech eligibility, timeouts and interruption.
#   Nova Chat says it DELIVERED in reply to one of this gateway's own requests (by request_id),
#   with its audit disposition attached. Never diagnostics, never empty/suppressed/cancelled ends.
"""voice_gateway/turns.py — pending requests, end classification and speech routing.

Request lifecycle (all keyed by the request_id the gateway generated, never by speaker name):
    sent -> acknowledged (user_message echo gives the server id, reply_to)
         -> answering (message_start carries the request_id)
         -> closed by message_end, request_end, an error, or the pending timeout.
Identity (Codex review #70): a reply is ours only if its request_id is pending, its reply_to equals the
acknowledged server id, and its message_id/run_id match the message_start seen for that request.
Interruption (a new utterance, barge-in, a stop) makes every earlier request ineligible: its late
final can close the request but is never spoken.
Speech policy (first stage, agreed in the Collaboration room #55-#70):
    * speak only delivery == "delivered" (scope "mine": request_id is ours; "replies": any reply to
      a human line, still identified by reply_to);
    * never speak empty / suppressed / cancelled / error / unsolicited ends — an error end carries a
      diagnostic, and unsolicited promotions need a policy of their own (Codex #65);
    * an end without `delivery` is old schema: silent, with one local "update Nova Chat" diagnostic;
    * delivered is not approved: audit {status, reason, source} rides along to captions;
      audit_gate="delivered" (default) speaks any delivered reply with its status attached,
      audit_gate="pass_only" speaks only an explicit PASS (NOT_RUN, CONCERN, INCOMPLETE, ERROR stay silent);
    * a new utterance, or the server's stop, flushes queued speech.
"""
from __future__ import annotations

import time
from collections import deque
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
    eligible: bool = True               # False once interrupted: its reply is never spoken
    why_not: str = ""
    delayed: bool = False


class VoiceSession:
    def __init__(self, cfg, player, body, *, clock=time.monotonic, log=print):
        self.cfg, self.player, self.body, self.clock, self.log = cfg, player, body, clock, log
        self.pending: dict[str, Pending] = {}
        self._by_message: dict[str, str] = {}
        self._old_schema_warned = False
        self._retired_replies = deque(maxlen=512)
        self.output_muted = False
        if getattr(cfg, "speak_from", "final") != "final":
            body.emit("diagnostic", level="warn",
                      message="speak_from='stream' is not part of the first stage; speaking delivered final "
                              "text only (no pre-audit speech).")
        player.on_idle = self._settle

    # ── outbound ──────────────────────────────────────────────────────────────────────────────
    def sent(self, request_id: str, text: str) -> None:
        """Cole spoke: stop what she is saying, retire every earlier request, wait for THIS one."""
        self._retire("new_request")
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
        self._retire("barge_in")

    def _retire(self, reason: str) -> None:
        """Interruption covers generations, not just audio: earlier requests stay pending only so
        their ends can close them, and are never spoken."""
        for p in self.pending.values():
            if p.eligible:
                p.eligible, p.why_not = False, f"interrupted ({reason})"
                self._turn(p, "interrupted", state="cancelled", eligible=False, why=p.why_not)
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

    def _on_start(self, ev):
        p = self.pending.get(ev.request_id) if ev.request_id else None
        if p is None:
            return
        if not p.reply_to or ev.reply_to != p.reply_to or not ev.message_id or not ev.run_id:
            self.body.emit("diagnostic", level="warn",
                           message=f"message_start for request {p.request_id[:8]} has identity that does not "
                                   f"match its acknowledgement; its reply will not be spoken.")
            return
        p.state = "answering"
        p.message_ids.add(ev.message_id)
        p.run_ids[ev.message_id] = ev.run_id
        self._by_message[ev.message_id] = p.request_id
        self._turn(p, "started", state="thinking", message_id=ev.message_id, run_id=ev.run_id)
        self.body.emit("state", state="thinking", request_id=p.request_id, message_id=ev.message_id,
                       run_id=ev.run_id)

    def _on_end(self, ev):
        if ev.delivery is None:
            if not self._old_schema_warned:
                self._old_schema_warned = True
                self.body.emit("diagnostic", level="error",
                               message="Nova Chat sent a reply end without delivery metadata (old server). "
                                       "Nothing from it is spoken; restart or update Nova Chat.")
            return
        request_id = ev.request_id
        pending = self.pending.get(request_id) if request_id else None
        identity = self._identity(pending, ev) if pending is not None else "not one of this gateway's requests"
        if pending is not None:
            self._close(request_id)
        eligible, why = self.classify(ev, pending, identity)
        units = []
        if eligible:
            units = [u.text for u in commit_block(speech_text(ev.text), min_chars=self.cfg.min_chars,
                                                  max_buffer=self.cfg.max_buffer)]
            units = [t for t in units if t.strip()]
            if not units:
                why = "nothing speakable after removing code, markers and links"
        # Policy and queueing only; whether audio actually played is in the speech events.
        self.body.emit("message", phase="end", message_id=ev.message_id, request_id=request_id,
                       run_id=ev.run_id, delivery=ev.delivery, audit=dict(ev.audit), eligible=eligible,
                       queued_units=len(units), why=why,
                       elapsed_s=round(self.clock() - pending.sent_at, 3) if pending else None)
        if pending is not None and not units:
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
    @staticmethod
    def _identity(p, ev) -> str:
        """'' when the end provably answers request p; otherwise why not."""
        if not p.reply_to:
            return "request never acknowledged (no user_message echo)"
        if ev.reply_to != p.reply_to:
            return "reply_to does not match the acknowledged request"
        if ev.message_id not in p.message_ids:
            return "no matching message_start for this message"
        if not ev.run_id or p.run_ids.get(ev.message_id) != ev.run_id:
            return "run_id does not match its message_start"
        return ""

    def classify(self, ev, pending=None, identity: str = "not one of this gateway's requests"):
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
            if not pending.eligible:
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
        Only one request can remain eligible, so retention cannot grow with conversation length.
        """
        limit = float(getattr(self.cfg, "request_timeout_s", 300))
        stale = []
        for rid, pending in list(self.pending.items()):
            if self.clock() - pending.sent_at <= limit:
                continue
            if pending.eligible and pending.reply_to:
                if not pending.delayed:
                    pending.delayed = True
                    self._turn(pending, "delayed", state="waiting",
                               why="Nova has accepted this request; waiting for the delayed reply")
                    self.body.emit("diagnostic", level="warn", request_id=rid,
                                   message=f"Nova's voice reply is taking longer than {int(limit)} s. "
                                           "Its reply will still be spoken unless interrupted or stopped.")
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
