# @nova: Retain actual current incoming requests and explicit tool constraints separately from internal corrections.
"""Pure per-generation context; no persisted state or inferred completion ledger."""
from copy import deepcopy
import json
import re


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


# Explicit imperative restrictions only. Mentioning files, quoting old instructions,
# or talking about a tool is not itself a request to execute one.
_DENY = re.compile(r"\b(?:use|using|with)\s+no\s+(?:external\s+)?tools?\b"
    r"|(?:^|[.!?;\n])\s*(?:please\s+)?no\s+(?:external\s+)?tools?\b"
    r"|\b(?:do\s+not|don't|don’t|never)\s+(?:use|call|run|invoke)\s+(?:any\s+)?(?:external\s+)?tools?\b"
    r"|\btools?\s+(?:are\s+)?(?:not\s+allowed|forbidden)\b", re.I)
_ALLOW = re.compile(r"\b(?:you\s+(?:can|may)\s+|please\s+)?use\s+(?:external\s+)?tools?\s+(?:now|again)\b"
                    r"|\btools?\s+(?:are\s+)?(?:now\s+)?allowed\b", re.I)


_VOICE_DELIVERY_EVIDENCE = (
    "VOICE DELIVERY EVIDENCE — this register routes your reply toward a voice adapter; it does "
    "not establish a live microphone, speaker, or listener. Incoming text, including an ASR "
    "transcript, establishes received wording, not microphone quality or a person hearing you. "
    "The CURRENT CANDIDATE is still a draft: it is not yet committed by this call's final or "
    "segment delivery callback. Streamed draft/progress text is not downstream playback "
    "evidence; no synthesis, playback, or listener acknowledgment for it is supplied here. "
    "Previously delivered segments mean TEXT handed to an adapter, not proven audio. A WAV "
    "receipt proves synthesis only; a correlated player-completion receipt proves reported "
    "device playback only; a person's explicit report supports attributed hearing, not your "
    "independent acoustic verification. Match any evidence to its request/segment and time: "
    "earlier hearing or playback cannot prove this draft was heard or a current audio test passed. "
    "Give the requested reply without adding unobserved delivery/test-success claims. Do not "
    "turn ordinary replies into audio disclaimers or audit discussion. Idiomatic acknowledgment "
    "('I hear you'), clearly quoted/requested wording, and accurately attributed recipient "
    "reports are different from asserting that the current output was played or heard."
)


def voice_delivery_context(register):
    """Known body/adapter boundary, not an inferred device status or a fabricated receipt."""
    return _VOICE_DELIVERY_EVIDENCE if register in ("voice", "voice_fast") else ""


class CurrentRequest:
    def __init__(self, entries=(), *, delivery_context=""):
        self.entries = deepcopy(list(entries))
        self.delivery_context = str(delivery_context)

    @classmethod
    def from_messages(cls, messages, *, delivery_context=""):
        # Compatibility fallback for callers lacking admission metadata. Older failed
        # or cancelled user rows are not automatically new instructions for this turn.
        latest = next((text_content(message.get("content")) for message in reversed(messages)
                       if message.get("role") == "user"), "")
        return cls([latest] if latest else [], delivery_context=delivery_context)

    @classmethod
    def from_entries(cls, entries, *, delivery_context=""):
        values = []
        for entry in entries:
            text = text_content(entry.get("content"))
            if entry.get("author"):
                text = f"{entry['author']} → you: {text}"
            values.append(text)
        return cls(values, delivery_context=delivery_context)

    def add(self, content):
        self.entries.append(text_content(content))

    def snapshot(self):
        return CurrentRequest(self.entries, delivery_context=self.delivery_context)

    @property
    def tools_forbidden(self):
        forbidden = False
        for text in self.entries:
            # Quoted wording/code is content to discuss, not a fresh tool restriction.
            text = re.sub(r"```.*?```|`[^`]*`|\"[^\"]*\"|(?<!\w)'[^'\n]*'(?!\w)|“[^”]*”|‘[^’]*’", "", text, flags=re.S)
            text = re.sub(r"^[^\n]{1,60}→ you:\s*", "", text)
            # Later explicit permission can change an earlier explicit restriction.
            signals = [(m.start(), True) for m in _DENY.finditer(text)]
            signals += [(m.start(), False) for m in _ALLOW.finditer(text)]
            for _, forbidden in sorted(signals):
                pass
        return forbidden

    @property
    def latest(self):
        return self.entries[-1] if self.entries else ""

    def render_step(self, *, turn_id, input_revision, delivered=(), completed_tool_count=0,
                    last_completed_action=None, attended_context=()):
        """Current generation state, not a verdict or a prediction of the next output choice."""
        state = {
            "turn_id": turn_id,
            "input_revision": input_revision,
            "applied_incoming_requests": deepcopy(self.entries),
            "committed_output_segments": list(delivered),
            "completed_tool_count": completed_tool_count,
            "last_completed_action": deepcopy(last_completed_action),
            # Attention is separately attributed context from the work owner, not
            # another admission or a claim that its assistant text was ours to deliver.
            "latest_attended_context": [{"role": item["role"],
                "content": text_content(item.get("content"))} for item in attended_context],
        }
        return ("[System] CURRENT WORK STEP — body state for this provider call.\n"
                + json.dumps(state, ensure_ascii=False) +
                "\nThe applied requests are this active work's inputs, in arrival order; "
                "the last entry is the latest applied input. Later changes amend earlier ones. "
                "Older NOW cards and request/correction snapshots describe earlier steps, not "
                "the current input state. Keep their relevant evidence and corrections, but "
                "answer the current requests above. Only committed_output_segments have been "
                "delivered by this work; other drafts are private intermediate work. Completed "
                "tool records describe actual outcomes, not permission to repeat actions. "
                "No final/progress choice is made for the next candidate here: choose the output "
                "control required by the remaining work and the actual requests. Do not repeat "
                "already delivered work or treat an internal correction as a new human goal.")

    def render(self, delivered=(), *, continuing=False):
        # Whole current requests survive here; context-budget anchors separately
        # preserve them in generation. This is not a model-generated summary.
        return ("CURRENT APPLIED INCOMING REQUESTS (ordered; later changes amend earlier ones):\n"
                + json.dumps(self.entries, ensure_ascii=False) +
                "\nALREADY DELIVERED SEGMENTS (do not repeat; these alone do not prove the remaining task complete):\n"
                + json.dumps(list(delivered), ensure_ascii=False) +
                "\n" + ("This candidate is a progress segment; assess its claims and relevance, not completion of all remaining work."
                           if continuing else "This candidate finishes the current work: answer every still-applicable request, including follow-ups not satisfied by delivered segments.") +
                "\nInternal audit/correction messages are NOT new human requests. Repair unsupported claims without dropping the requested content or narrating the audit. "
                "Requests to say a phrase are evidence of requested wording, not proof of a real-world test or action. "
                + ("No external tools or file reads are allowed for this current request, including auditor reads. Use supplied evidence; qualify unsupported claims."
                   if self.tools_forbidden else "Verification tools may be used only when relevant and permitted by the actual request.")
                + ("\n" + self.delivery_context if self.delivery_context else ""))
