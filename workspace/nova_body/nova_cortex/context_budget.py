# @nova: Fit text context without losing the current request or persisted task checkpoint to tool-output clipping.
"""Pure text-budget estimation; image tokens and exact tokenizer costs remain provider-dependent."""
from copy import deepcopy
import re

CONTINUITY_START = "--- TASK CONTINUITY ---"
CONTINUITY_END = "--- END TASK CONTINUITY ---"
OMITTED = "\n[context shortened; use task records or smaller file reads for omitted details]\n"


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content
                       if isinstance(part, dict) and isinstance(part.get("text"), str))
    return ""


def text_size(messages):
    return sum(len(content_text(message.get("content"))) for message in messages)


def prompt_char_budget(ctx_limit=65536, max_output=16384, prompt_max=174000):
    # Keep the established 3.4 chars/token estimate, with 4096 tokens for template,
    # estimation error and other overhead. This is not exact tokenizer accounting.
    tokens = int(ctx_limit) - int(max_output) - 4096
    if tokens <= 0:
        raise ValueError("Context window must exceed output reserve plus 4096 tokens")
    return min(int(prompt_max), int(tokens * 3.4))


def _clip_text(text, limit, preserve_checkpoint=False):
    limit = max(0, int(limit))
    if len(text) <= limit:
        return text
    marker = OMITTED[:limit]
    available = limit - len(marker)
    if preserve_checkpoint:
        start = text.find(CONTINUITY_START)
        end = text.find(CONTINUITY_END, start + len(CONTINUITY_START)) if start >= 0 else -1
        if end >= 0:
            end += len(CONTINUITY_END)
            checkpoint = text[start:end]
            if len(checkpoint) <= available:
                # Retain the normal instruction prefix plus the whole checkpoint even
                # when identity/memory files have pushed that checkpoint to the tail.
                other = text[:start] + text[end:]
                return other[:available - len(checkpoint)] + marker + checkpoint
    return text[:available] + marker


def _clip_message(message, limit):
    message = deepcopy(message)
    content = message.get("content", "")
    if isinstance(content, str):
        message["content"] = _clip_text(content, limit, message.get("role") == "system")
    elif isinstance(content, list):
        # Keep image parts unchanged; cap the combined textual parts, not each part.
        remaining = max(0, int(limit))
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                part["text"] = _clip_text(part["text"], remaining)
                remaining -= len(part["text"])
    return message


def _current_request(messages):
    users = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    # Nova Chat labels human/peer turns. Tool results are also role=user, so the
    # newest role=user alone may be a receipt rather than the request being served.
    labelled = [i for i in users if re.match(r"^[^\n]{1,100} → you:", content_text(messages[i].get("content")))]
    if labelled:
        return labelled[-1]
    actual = [i for i in users if not content_text(messages[i].get("content")).startswith(
        ("[System ", "[System:", "Screenshot from "))]
    return (actual or users or [None])[-1]


def fit_messages(messages, *, max_chars=174000, per_message=24000):
    """Bound all text, preserving system context, current request and newest turn.

    Ordinary messages are capped individually; systems are only shortened if the
    total budget requires it. Older history goes first. No minimum-turn override
    may silently exceed the budget. Extremely small budgets can still shorten
    critical content and visibly mark the omission.
    """
    budget = max(0, int(max_chars))
    cap = max(0, int(per_message))
    fitted = [deepcopy(m) if m.get("role") == "system" else _clip_message(m, cap)
              for m in messages]
    current = _current_request(fitted)
    newest = next((i for i in range(len(fitted) - 1, -1, -1)
                   if fitted[i].get("role") != "system"), None)
    protected = {i for i in (current, newest) if i is not None}
    kept = list(range(len(fitted)))
    total = text_size(fitted)
    for index, message in enumerate(fitted):
        if total <= budget:
            break
        if message.get("role") != "system" and index not in protected:
            kept.remove(index)
            total -= len(content_text(message.get("content")))
    # Once dispensable history is gone, shorten the system's excess grounding
    # context. Normal 64K budgets leave room for its instruction prefix/checkpoint
    # and two individually capped live turns. Multiple system messages share it.
    for index in kept:
        if total <= budget:
            break
        message = fitted[index]
        if message.get("role") == "system":
            size = len(content_text(message.get("content")))
            shortened = _clip_message(message, max(0, size - (total - budget)))
            total -= size - len(content_text(shortened.get("content")))
            fitted[index] = shortened
    # Only exceptional tiny budgets reach this path. Preserve the current request
    # ahead of a newer tool receipt; never resurrect overflow to keep N turns.
    for index in sorted(protected, key=lambda i: i == current):
        if total <= budget:
            break
        size = len(content_text(fitted[index].get("content")))
        shortened = _clip_message(fitted[index], max(0, size - (total - budget)))
        total -= size - len(content_text(shortened.get("content")))
        fitted[index] = shortened
    return [fitted[i] for i in kept]
