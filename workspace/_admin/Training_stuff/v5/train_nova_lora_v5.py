#!/usr/bin/env python3
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
# DATA (243 rows):
#   nova_core_v2.jsonl            108  original voice
#   nova_core_v3_additions.jsonl   59  multi-turn + autonomy (existence/deciding)
#   nova_core_v5_stance.jsonl      76  NEW — verify-under-pressure + tools-as-senses
#       60/76  reach for a tool UNPROMPTED (reflex, not rebuttal)
#       31/76  RE-RUN a tool after being challenged   <-- v4 had ZERO
#       33/76  escalate to a SECOND, different tool (cross-check)
#       19/76  UPDATE cleanly when the tool proves COLE right  <-- anti-contrarian counterweight
#        0     real Nova filenames baked into weights
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
assert "{% generation %}" in tok.chat_template, "template missing generation markers"

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
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,        # effective batch 8 -> ~30 steps/epoch at 243 rows
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
