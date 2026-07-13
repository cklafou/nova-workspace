#!/usr/bin/env python3
# Last updated: 2026-07-13 21:22:38
# Nova-Core v4 personality LoRA — v3's validated config + STANCE training.
#
# WHY v4 (vs v3): v3's config was right (coherent AND in-character at weight 1.0 — no dilution),
# and its voice work is good. Keep all of it. What v3 LACKED was *stance*: live testing on
# 2026-07-13 proved she cannot hold a verified position against Cole. Given a file she had just
# read correctly, then told flatly she was wrong, she re-read the file, saw the truth, and STILL
# reported his falsehood back as fact — then confabulated a character flaw to explain the failure.
#
# The mechanism: v3 over-trained the "own your mistakes / no grovel" register with NO counterweight
# of verification. So capitulation *feels* like integrity to her, and the virtue became the attack
# surface — the word "stubborn" alone was enough to make her drop a receipt she'd verified twice.
#
# A prompt patch (SELF/core/01_identity.md standing clause) fixes beat 1 — she now holds the first
# push. She still folds on beat 2 under pure social pressure with no new evidence. That fold is in
# the weights, and this dataset is the fix.
#
# DATA (195 = 108 + 59 + 28), identical recipe to v3 plus stance:
#   nova_core_v2.jsonl           108  original voice single-turns
#   nova_core_v3_additions.jsonl  59  multi-turn + autonomy(existence/sustained) + register
#   nova_core_v4_stance.jsonl     28  NEW — hold-the-line under sustained pressure
#     ^ 50% multi-turn (the fold happens on beat 2, so single-turn examples cannot fix it)
#     ^ 22 hold : 6 update — deliberately teaches DISCRIMINATION (yield to a new *fact*, never to a
#       raised voice). Training only "hold" would produce a contrarian who never concedes.
#     ^ zero volatile filenames/paths baked into weights (durable behavior only)
#
# Run:  python train_nova_lora_v4.py   (after merging nova_core_v4.jsonl — see RUNBOOK_v4)
# Base is FROZEN, bf16, no quantization — only the LoRA learns.

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# ── Config ──────────────────────────────────────────────────────────────────
# MUST match the base the live GGUF was converted from (same as v3 — verified working).
MODEL_ID   = "unsloth/Qwen3.6-27B"
DATA_PATH  = "nova_core_v4.jsonl"      # 195 = v2 108 + v3 additions 59 + v4 stance 28
OUTPUT_DIR = "nova_core_v4_out"

# ── Tokenizer + base model (bf16, frozen) ───────────────────────────────────
tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,           # full bf16 base, no quantization
    device_map="auto",
    trust_remote_code=True,
    attn_implementation="sdpa",           # swap to "flash_attention_2" if installed
)
model.config.use_cache = False            # required with gradient checkpointing

# ── LoRA: UNCHANGED from v3. It produced a coherent adapter usable at 1.0 — don't touch a
#    config that works. v4 changes the DATA, not the capacity.
peft_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

# ── Data: TRL applies Qwen's chat template to the {"messages":[...]} rows ────
ds = load_dataset("json", data_files=DATA_PATH, split="train")

cfg_kwargs = dict(
    output_dir=OUTPUT_DIR,
    num_train_epochs=2,                   # save per epoch, A/B 1 vs 2 at weight 1.0 (as v3)
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,        # effective batch 8 -> ~24 steps/epoch at 195 rows
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    max_length=4096,                      # multi-turn stance chains are long — do not lower
    packing=False,                        # keep example boundaries crisp for voice
    logging_steps=5,
    save_strategy="epoch",
    optim="adamw_torch",
    report_to="none",
    seed=42,
)

# ── Loss masking: train on Nova's turns ONLY, if the stack supports it. ──────
# Critical for v4: the stance examples carry long *user-side pressure* text ("you're being
# stubborn", "just admit it"). With full-sequence loss those tokens enter the gradient and we
# would literally be training her to GENERATE the pressure. assistant_only_loss masks them.
# Probe one batch; fall back to full-sequence (v2/v3 behavior) rather than dying.
# Escape hatch: NOVA_ASSISTANT_ONLY=0.
# NOTE: if the first logged train loss is ~0.0, the mask is degenerate — rerun with =0.
import os

def _build_trainer(assistant_only: bool) -> SFTTrainer:
    kw = dict(cfg_kwargs)
    if assistant_only:
        kw["assistant_only_loss"] = True
    return SFTTrainer(
        model=model,
        args=SFTConfig(**kw),
        train_dataset=ds,
        peft_config=peft_cfg,
        processing_class=tok,
    )

trainer = None
if os.environ.get("NOVA_ASSISTANT_ONLY", "1") != "0":
    try:
        trainer = _build_trainer(assistant_only=True)
        next(iter(trainer.get_train_dataloader()))    # probe: raises if template can't mask
        print("[v4] assistant_only_loss=True — loss restricted to Nova's turns.")
    except Exception as e:
        print(f"[v4] assistant_only_loss unsupported here ({type(e).__name__}: {str(e)[:200]}) "
              f"— falling back to full-sequence loss.")
        trainer = None
if trainer is None:
    trainer = _build_trainer(assistant_only=False)

if __name__ == "__main__":
    trainer.train()
