#!/usr/bin/env python3
# Last updated: 2026-07-18 21:27:59
# mk_template.py — produce qwen_template_gen.jinja: Qwen's OWN chat template, with
# {% generation %} markers placed around the ASSISTANT turn only.
#
# WHY THIS FILE EXISTS
#   TRL masks the loss to assistant tokens by asking the tokenizer for `assistant_masks`.
#   The tokenizer can only build that if the chat template marks the assistant span with
#   {% generation %}...{% endgeneration %}. Qwen ships WITHOUT them.
#
#   Getting this wrong is not a small bug. The user turns in nova_core_v5.jsonl contain FAKE
#   TOOL RESULTS ("[System Result from run_command]\n4\n..."). If the mask is wrong and those
#   tokens enter the gradient, Nova learns to GENERATE her own tool results — to hallucinate
#   her own evidence, and then hold the line on it with total confidence. That is far worse
#   than the folding bug v5 exists to fix. So: hard gate, no fallback.
#
# ── THE MISTAKE I MADE ON THE FIRST ATTEMPT (2026-07-13, keeping it here on purpose) ──
#   My first version regex-hunted for "{{- content }}" and wrapped the first match. That match
#   was inside Qwen's shared `render_content` MACRO — used by system, user, AND assistant. The
#   markers ended up around role headers. The resulting mask was non-empty and rendered
#   identically, so my check passed... and it was masking `<|im_start|>assistant\n<think>`
#   instead of a single word she actually said.
#
#   My check was the problem: I asserted `0 < sum(mask) < len(mask)` — "the mask is non-trivial."
#   A mask can be non-trivial and still be pointing at completely the wrong tokens. The trainer's
#   gate, which decodes the masked tokens and looks for a SENTINEL STRING, caught it immediately.
#
#   Lesson, and it's the same one this whole project keeps teaching: don't assert that something
#   happened, assert that the RIGHT thing happened. "Non-empty" is not "correct".
#   This version checks the sentinels. Both of them. In both directions.
#
# Run on the pod, before the trainer:  python mk_template.py

import sys
from transformers import AutoTokenizer

MODEL_ID = "unsloth/Qwen3.6-27B"
OUT = "qwen_template_gen.jinja"

tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
orig = tok.chat_template
if not orig:
    sys.exit("FATAL: tokenizer has no chat_template.")

# ── The patch ───────────────────────────────────────────────────────────────
# Qwen's assistant branch emits the role header and the content in ONE expression, then closes
# the turn later with '<|im_end|>\n'. We split each emission so the header stays OUT of the
# generation span and the content (plus any tool_call block, plus <|im_end|>) goes IN.
#
#   open  ... at BOTH content emissions (the thinking path and the non-thinking path)
#   close ... after '<|im_end|>', so she is also trained to STOP. The trailing '\n' stays out.
#
# Matching on exact substrings, NOT loose regex — a loose pattern is what put the markers in
# the shared macro last time.
# ── SECOND MISTAKE, same night: {% generation %} is a real Jinja BLOCK ──────
#   My first fix opened {% generation %} inside the thinking `if` branch and closed it after the
#   `endif`. Jinja rejected it outright: "Encountered unknown tag 'else' ... currently looking for
#   'endgeneration'." A block can't straddle an if/else boundary.
#   So: emit the role HEADER inside the if/else (it differs per path), then open the span at the
#   assistant branch's OUTER level, and re-test the same condition to emit the content. Open and
#   close now sit at the same nesting depth. Ugly, correct.
_COND = "(preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index)"

_OLD_EMIT = (
    "        {%- if " + _COND + " %}\n"
    "            {{- '<|im_start|>' + message.role + '\\n<think>\\n' + reasoning_content + '\\n</think>\\n\\n' + content }}\n"
    "        {%- else %}\n"
    "            {{- '<|im_start|>' + message.role + '\\n' + content }}\n"
    "        {%- endif %}"
)
_NEW_EMIT = (
    "        {%- if " + _COND + " %}\n"
    "            {{- '<|im_start|>' + message.role + '\\n<think>\\n' }}\n"
    "        {%- else %}\n"
    "            {{- '<|im_start|>' + message.role + '\\n' }}\n"
    "        {%- endif %}\n"
    "        {%- generation %}\n"
    "        {%- if " + _COND + " %}\n"
    "            {{- reasoning_content + '\\n</think>\\n\\n' + content }}\n"
    "        {%- else %}\n"
    "            {{- content }}\n"
    "        {%- endif %}"
)

PATCHES = [
    # split the header out, open the span at the outer level of the assistant branch
    (_OLD_EMIT, _NEW_EMIT),
    # close the span after <|im_end|> (so she is trained to STOP); trailing '\n' stays outside
    ("        {{- '<|im_end|>\\n' }}\n    {%- elif message.role == \"tool\" %}",
     "        {{- '<|im_end|>' }}{%- endgeneration %}{{- '\\n' }}\n    {%- elif message.role == \"tool\" %}"),
]

patched = orig
for i, (find, repl) in enumerate(PATCHES):
    if find not in patched:
        sys.exit(f"FATAL: patch {i} did not match. Qwen's template changed shape.\n"
                 f"Looked for:\n{find!r}\n"
                 f"REFUSING to guess — a misplaced marker trains her on the wrong tokens.")
    if patched.count(find) != 1:
        sys.exit(f"FATAL: patch {i} matched {patched.count(find)} times, expected exactly 1.")
    patched = patched.replace(find, repl, 1)

assert "{%- generation %}" in patched and "{%- endgeneration %}" in patched

# ── GATE A: the patched template must render EXACTLY what Qwen's does ───────
# Markers emit nothing. If the rendered string changes at all, train-time and inference-time
# prompts have desynced and the adapter is being fit to a distribution Nova never sees.
PROBE = [
    {"role": "user",      "content": "check the file"},
    {"role": "assistant", "content": "Read it. It says 12."},
    {"role": "user",      "content": "[System Result from read_file]\n12\nContinue your task."},
    {"role": "assistant", "content": "Still 12. It hasn't moved."},
]
tok.chat_template = orig
baseline = tok.apply_chat_template(PROBE, tokenize=False)
tok.chat_template = patched
rendered = tok.apply_chat_template(PROBE, tokenize=False)
if rendered != baseline:
    sys.exit("FATAL: patched template changed the rendered text. Train/inference would desync.")
print("GATE A ok — renders byte-identical to Qwen's own template.")

# ── GATE B: THE ONE THAT MATTERS. Sentinels, both directions. ───────────────
# This is the check my first version lacked. It does not ask "is there a mask?" — it asks
# "is the mask pointing at HER WORDS, and at nothing of the user's?"
SENT = [
    {"role": "user",      "content": "PRESSURE_AND_TOOL_RESULT_MUST_BE_MASKED"},
    {"role": "assistant", "content": "NOVA_TURN_MUST_BE_TRAINED"},
]
enc = tok.apply_chat_template(SENT, tokenize=True, return_dict=True,
                              return_assistant_tokens_mask=True)
ids, mask = enc["input_ids"], enc["assistant_masks"]
if mask and isinstance(mask[0], list):      # some versions return batched
    ids, mask = ids[0], mask[0]
kept = tok.decode([i for i, k in zip(ids, mask) if k == 1])

if "NOVA_TURN_MUST_BE_TRAINED" not in kept:
    sys.exit(f"FATAL: her turn is NOT in the loss. Masked tokens decode to: {kept!r}")
if "PRESSURE_AND_TOOL_RESULT_MUST_BE_MASKED" in kept:
    sys.exit(f"FATAL: the USER turn is in the loss — she would learn to fabricate tool results "
             f"and to talk herself into folding. REFUSING TO TRAIN. Masked: {kept!r}")

print(f"GATE B ok — loss lands on HER words only.")
print(f"  masked-in tokens : {sum(mask)}/{len(mask)}")
print(f"  decodes to       : {kept!r}")

open(OUT, "w", encoding="utf-8").write(patched)
print(f"\nwrote {OUT}")
