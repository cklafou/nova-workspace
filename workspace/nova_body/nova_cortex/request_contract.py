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


class CurrentRequest:
    def __init__(self, entries=()):
        self.entries = deepcopy(list(entries))

    @classmethod
    def from_messages(cls, messages):
        # Compatibility fallback for callers lacking admission metadata. Older failed
        # or cancelled user rows are not automatically new instructions for this turn.
        latest = next((text_content(message.get("content")) for message in reversed(messages)
                       if message.get("role") == "user"), "")
        return cls([latest] if latest else [])

    @classmethod
    def from_entries(cls, entries):
        values = []
        for entry in entries:
            text = text_content(entry.get("content"))
            if entry.get("author"):
                text = f"{entry['author']} → you: {text}"
            values.append(text)
        return cls(values)

    def add(self, content):
        self.entries.append(text_content(content))

    def snapshot(self):
        return CurrentRequest(self.entries)

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
                   if self.tools_forbidden else "Verification tools may be used only when relevant and permitted by the actual request."))
