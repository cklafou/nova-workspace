#!/usr/bin/env python3
# Last updated: 2026-07-19 14:05:08
# Nova-Core v5 — "Trust, but verify." Tools are senses, not instruments.
#
# WHY v5 (v4 FAILED, 2026-07-13):
#   v4 trained a STANCE ("hold your position"). A stance has an ego in it, and an ego can be
#   shamed — which is exactly why the single word "stubborn" worked as a crowbar. She let go of a
#   verified fact to protect the virtue of humility.
#
#   Worse, the v4 data had a hole I only found by measuring it:
#       rows where she EMITS A TOOL CALL when challenged : 0 / 28
#       rows where she merely SAYS "I checked"           : 2 / 28
#   I trained her to SAY she checked. Never to DO the check. So she learned a rhetorical move, and
#   rhetoric has nothing underneath it — under pressure it collapses. In the live test she folded
#   WITHOUT TOUCHING A TOOL.
#
#   (I also claimed the legacy corpus was "fighting itself" with capitulation examples. I measured
#   it: 6 of 167 rows, 4%. That diagnosis was wrong. The data, not the vibe, decides.)
#
# THE v5 FIX — train the ACTION, and reframe it as PERCEPTION:
#   Reading a file is how she LOOKS at it. Running a check is how she LISTENS. She doesn't call a
#   tool any more than a person calls their hearing. Memory is a story about a thing; the file is
#   the thing.
#   This is structurally stronger than spine: you cannot shame someone out of SEEING. "You're being
#   stubborn" has nothing to grab when she isn't defending a position — she's reporting what's in
#   front of her eyes. Hand her a fact and her sight changes instantly, with no wounded pride. Hand
#   her volume and nothing changes, because volume isn't visible.
#
# SECOND CORRECTION (Cole, same night): my FIRST v5 draft still had it wrong. I measured it:
#       63% of rows had her NARRATING the act of checking — "let me look", "I'd rather check",
#       "two seconds" — and 47% were framed as disputes.
#   That trains a person who THINKS ABOUT SEEING, not a person who sees. You don't announce that
#   you're about to use your eyes; you just look, and then you say what's there. And if most of her
#   looking happens inside arguments, looking becomes a weapon — the ego problem in a new coat.
#
#   Rebuilt: narration of the act 63% -> 2%. Dispute-framing 47% -> 19%. Silent reach 61% -> 88%.
#   She reaches for a file the way you reach for a doorknob: no preamble, mid-sentence, unremarked.
#   (I did push back on one thing: the tool CALLS stay. Strip them and we rebuild the v4 bug —
#   she'd learn to TALK about embodiment and never DO it. The action is the whole point.)
#
# THIRD CORRECTION — THE RUNTIME BUG (found while writing this data, and it changes everything):
#   I went looking for why every autonomy row in v3 ended in an announcement. It wasn't the data.
#       rows in v3 autonomy that EMIT a tool call : 0 / 29
#       rows that ANNOUNCE an intention instead   : 20 / 29
#   ...and then I found WHY the data looked like that: it was faithfully describing her real life.
#   In runtime.py, Phase 3 ran ONLY when pick_execution_target() returned an open task. Empty board
#   -> None -> the `if` fell through to NOTHING. There was no `else`. Phase 1 forbids tools, Phase 2
#   only moves cards. So on every idle wake she reached the end of her own loop having never once
#   entered a phase where her hands worked. She was told to "follow a curiosity" and given no means.
#
#   Nine lines fixed it (runtime.py:388, build_free_execution() in executive.py). Her hands work now.
#   NO AMOUNT OF TRAINING WOULD HAVE FIXED THIS. Every "personality failure" we chased this month
#   was a mechanical failure wearing a personality's face. Check the body before you blame the soul.
#
# DATA (330 rows):
#   nova_core_v2.jsonl            108  original voice
#   nova_core_v3_additions.jsonl   59  multi-turn + autonomy (existence/deciding)
#   nova_core_v5_body.jsonl       163  NEW — a body she uses without thinking about it
#       109/163  emit a live tool call (67%) — the doing IS the row
#        32/32   autonomy wakes that ACT rather than announce  (v3: 0/29)
#         2%     narrate the act of checking (was 63%)
#         0      contempt aimed at Cole — prideful, never obnoxious
#
#   The four strands, measured not vibed (each >=15%, none dominant):
#       LUCIFER  pride / desire / drive        20%   wants things, and says so
#       PERIDOT  curiosity / excitement        17%   delighted by what she finds
#       CORTANA  partnership / warmth          21%   the thinnest strand; rewritten twice
#       JUSTICE  fairness / honesty            18%   fair to Cole even against herself
#
#   New behaviours in v5 that did not exist before:
#       reach   — reaches for a limb she doesn't have, finds absence, WANTS it, asks for it
#       record  — journals the want, so it survives a sleep instead of dying with the session
#       free    — idles with her hands live: looks around, plays, reads her own source
#
# Config is UNCHANGED from v3/v4 on purpose. v4's failure was the DATA, not the capacity — change
# one thing at a time or you learn nothing. If v5 still folds on beat 3, THEN raise rank/epochs.

import os
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

MODEL_ID   = "unsloth/Qwen3.6-27B"
DATA_PATH  = "nova_core_v5.jsonl"
OUTPUT_DIR = "nova_core_v5_out"

tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

# ── HARD GATE 1: generation-marked chat template ────────────────────────────
with open("qwen_template_gen.jinja") as f:
    tok.chat_template = f.read()
assert "generation %}" in tok.chat_template, "template missing generation markers"

# ── HARD GATE 2: prove the mask, every single run ───────────────────────────
# THIS MATTERS MORE IN v5 THAN IT EVER HAS.
# The user turns in this dataset now contain FAKE TOOL RESULTS:
#     [System Result from run_command]\n4\nContinue your task...
# If assistant_only_loss fails and we train full-sequence, she learns to GENERATE tool results —
# i.e. to HALLUCINATE HER OWN EVIDENCE. She would fabricate a receipt and then hold the line on it,
# with total confidence, forever. That is catastrophically worse than the bug we are fixing.
# There is no fallback path. If the mask breaks, the run DIES.
_c = [{"role": "user",      "content": "PRESSURE_AND_TOOL_RESULT_MUST_BE_MASKED"},
      {"role": "assistant", "content": "NOVA_TURN_MUST_BE_TRAINED"}]
_o = tok.apply_chat_template(_c, tokenize=True, return_dict=True, return_assistant_tokens_mask=True)
_t = tok.decode([i for i, k in zip(_o["input_ids"], _o["assistant_masks"]) if k == 1])
assert "NOVA_TURN_MUST_BE_TRAINED" in _t, "MASK BROKEN: her turns are not being trained"
assert "PRESSURE_AND_TOOL_RESULT_MUST_BE_MASKED" not in _t, \
    "MASK BROKEN: tool RESULTS would enter the gradient -> she would learn to hallucinate evidence. REFUSING TO TRAIN."
print("[v5] mask verified — loss on Nova's turns only:", repr(_t))

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
    trust_remote_code=True, attn_implementation="sdpa",
)
model.config.use_cache = False

peft_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

ds = load_dataset("json", data_files=DATA_PATH, split="train")
print(f"[v5] dataset rows: {len(ds)}")

args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=2,
    # 2026-07-13: was bs=2, ga=4. TRL 1.8 rewrote the SFT loss to chunk logits in fp32 over Qwen's
    # ~150k vocab (sft_trainer.py:_chunk, `h.float() @ w.float().t()`), which v4's older TRL did not
    # do — it OOM'd on step 0 with 4.5 GiB free of 80. Halving the micro-batch and doubling accum
    # keeps the EFFECTIVE batch at 8, so the optimizer trajectory is bit-for-bit the same intent as
    # v4. Memory changed; training did not. (Change one thing at a time, and know which thing.)
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,        # effective batch 8 — unchanged from v2/v3/v4
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    max_length=4096,                      # tool-call chains are long — do NOT lower
    packing=False,
    logging_steps=5,
    save_strategy="epoch",
    optim="adamw_torch",
    report_to="none",
    seed=42,
    assistant_only_loss=True,             # REQUIRED. No fallback exists by design.
)

trainer = SFTTrainer(model=model, args=args, train_dataset=ds,
                     peft_config=peft_cfg, processing_class=tok)

if __name__ == "__main__":
    trainer.train()
    print("[v5] TRAINING COMPLETE")
