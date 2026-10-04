# Last updated: 2026-10-04 14:00:46
# @nova: Builds a loss-masking chat template for LoRA training from the base model's own template, refusing to train if it cannot prove the mask.
"""Generation-marked chat template + mask gates, generalised from v7's mk_template.py.

The trainer's assistant-only loss needs `{% generation %}` markers around the assistant's own
output in the chat template. Qwen ships templates without them, and they change between
releases (3.6 -> 3.8 changed the thinking condition and added reasoning-effort text), so a
fixed string patch breaks on every new model. This locates the assistant-emit block by
structure instead, then PROVES the result before any GPU time is spent:

  GATE A  the marked template renders byte-identical to the official one on several probes
          (multi-turn, system prompt, reasoning, tool call + tool result, thinking on/off).
  GATE B  the assistant-token mask keeps the assistant's words and drops user/tool text.

Any mismatch exits non-zero with the reason. There is no fallback: a misplaced marker would
train the model on user turns or fabricated tool results.

Usage:  python template_gen.py BASE_MODEL_ID OUT.jinja
"""
import json
from pathlib import Path
import re
import sys

EMIT_RE = re.compile(
    r"(?P<i1>[ \t]*)\{%- if (?P<cond>[^\n]+?) %\}\n"
    r"(?P<i2>[ \t]*)\{\{- '<\|im_start\|>' \+ message\.role \+ '\\n<think>\\n' \+ reasoning_content \+ '\\n</think>\\n\\n' \+ content \}\}\n"
    r"(?P<i3>[ \t]*)\{%- else %\}\n"
    r"(?P<i4>[ \t]*)\{\{- '<\|im_start\|>' \+ message\.role \+ '\\n' \+ content \}\}\n"
    r"(?P<i5>[ \t]*)\{%- endif %\}"
)
END_RE = re.compile(
    r"(?P<i>[ \t]*)\{\{- '<\|im_end\|>\\n' \}\}\n(?P<j>[ \t]*)\{%- elif message\.role == \"tool\" %\}"
)


def _emit(m):
    g = m.groupdict()
    return (
        f"{g['i1']}{{%- if {g['cond']} %}}\n"
        f"{g['i2']}{{{{- '<|im_start|>' + message.role + '\\n<think>\\n' }}}}\n"
        f"{g['i3']}{{%- else %}}\n"
        f"{g['i4']}{{{{- '<|im_start|>' + message.role + '\\n' }}}}\n"
        f"{g['i5']}{{%- endif %}}\n"
        f"{g['i1']}{{%- generation %}}\n"
        f"{g['i1']}{{%- if {g['cond']} %}}\n"
        f"{g['i2']}{{{{- reasoning_content + '\\n</think>\\n\\n' + content }}}}\n"
        f"{g['i3']}{{%- else %}}\n"
        f"{g['i4']}{{{{- content }}}}\n"
        f"{g['i5']}{{%- endif %}}"
    )


def _end(m):
    return (f"{m.group('i')}{{{{- '<|im_end|>' }}}}{{%- endgeneration %}}{{{{- '\\n' }}}}\n"
            f"{m.group('j')}{{%- elif message.role == \"tool\" %}}")


def mark(template: str) -> str:
    """Return the generation-marked template, or raise ValueError naming what failed."""
    for name, rx in (("assistant emit block", EMIT_RE), ("assistant end + tool branch", END_RE)):
        n = len(rx.findall(template))
        if n != 1:
            raise ValueError(f"{name}: found {n} matches, need exactly 1. The template changed shape; "
                             "refusing to guess where the assistant's words are.")
    marked = EMIT_RE.sub(_emit, template, count=1)
    marked = END_RE.sub(_end, marked, count=1)
    if "{%- generation %}" not in marked or "{%- endgeneration %}" not in marked:
        raise ValueError("generation markers missing after patching")
    return marked


TOOL_CALL = {"type": "function", "function": {"name": "read_file", "arguments": {"path": "a.txt"}}}
PROBES = [
    [{"role": "user", "content": "check the file"},
     {"role": "assistant", "content": "Read it. It says 12."},
     {"role": "user", "content": "[System Result from read_file]\n12\nContinue your task."},
     {"role": "assistant", "content": "Still 12. It hasn't moved."}],
    [{"role": "system", "content": "You are Nova."},
     {"role": "user", "content": "hi"},
     {"role": "assistant", "content": "Hey."}],
    [{"role": "user", "content": "think first"},
     {"role": "assistant", "content": "Done.", "reasoning_content": "Short plan."},
     {"role": "user", "content": "again"},
     {"role": "assistant", "content": "Done again.", "reasoning_content": "Same plan."}],
    [{"role": "user", "content": "open a.txt"},
     {"role": "assistant", "content": "", "tool_calls": [TOOL_CALL]},
     {"role": "tool", "content": "12"},
     {"role": "assistant", "content": "It says 12."}],
]
RENDER_KWARGS = [{}, {"enable_thinking": False}, {"add_generation_prompt": True}]


def gates(tok, official: str, marked: str) -> str:
    """GATE A + GATE B. Returns a short report; raises ValueError on any failure."""
    checked = 0
    for probe in PROBES:
        for kw in RENDER_KWARGS:
            try:
                tok.chat_template = official
                want = tok.apply_chat_template(probe, tokenize=False, **kw)
            except Exception:
                continue  # the official template rejects this probe/kwarg combination itself
            tok.chat_template = marked
            got = tok.apply_chat_template(probe, tokenize=False, **kw)
            if got != want:
                raise ValueError(f"GATE A failed: marked template renders differently for probe "
                                 f"{PROBES.index(probe)} with {kw}. Training and inference would desync.")
            checked += 1
    if checked < 6:
        raise ValueError(f"GATE A could only check {checked} renders; not enough evidence.")
    tok.chat_template = marked
    sent = [{"role": "user", "content": "USER_TEXT_MUST_BE_MASKED"},
            {"role": "assistant", "content": "ASSISTANT_TEXT_MUST_BE_TRAINED"},
            {"role": "user", "content": "[System Result from read_file]\nTOOL_RESULT_MUST_BE_MASKED"},
            {"role": "assistant", "content": "SECOND_ANSWER_MUST_BE_TRAINED"}]
    enc = tok.apply_chat_template(sent, tokenize=True, return_dict=True, return_assistant_tokens_mask=True)
    ids, mask = enc["input_ids"], enc["assistant_masks"]
    if mask and isinstance(mask[0], list):
        ids, mask = ids[0], mask[0]
    kept = tok.decode([i for i, k in zip(ids, mask) if k == 1])
    for must in ("ASSISTANT_TEXT_MUST_BE_TRAINED", "SECOND_ANSWER_MUST_BE_TRAINED"):
        if must not in kept:
            raise ValueError(f"GATE B failed: assistant text is not in the loss. Kept: {kept!r}")
    for never in ("USER_TEXT_MUST_BE_MASKED", "TOOL_RESULT_MUST_BE_MASKED"):
        if never in kept:
            raise ValueError(f"GATE B failed: {never} would be trained. Kept: {kept!r}")
    return f"GATE A ok ({checked} renders identical); GATE B ok ({sum(mask)}/{len(mask)} tokens trained)"


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    from transformers import AutoConfig, AutoTokenizer
    # Resolve one immutable HF revision for template, tokenizer, weights and conversion config.
    from huggingface_hub import model_info
    revision = model_info(argv[1]).sha
    config = AutoConfig.from_pretrained(argv[1], revision=revision, trust_remote_code=False)
    if not revision:
        raise ValueError("Unable to pin the base model revision")
    tok = AutoTokenizer.from_pretrained(argv[1], revision=revision, trust_remote_code=False)
    official = tok.chat_template
    if not official:
        print("FATAL: the tokenizer has no chat template", file=sys.stderr)
        return 1
    try:
        marked = mark(official)
        report = gates(tok, official, marked)
    except ValueError as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1
    with open(argv[2], "w", encoding="utf-8") as fh:
        fh.write(marked)
    Path("base_config").mkdir(exist_ok=True)
    config.save_pretrained("base_config")
    Path("base_source.json").write_text(json.dumps({"model_id": argv[1], "revision": revision,
        "model_type": config.model_type, "architectures": config.architectures}, indent=2) + "\n", encoding="utf-8")
    print(report)
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
