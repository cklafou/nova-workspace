#!/usr/bin/env python3
# Last updated: 2026-07-08 08:56:41
# Nova-Core v3 personality LoRA — corrected config (style adapter, not a brain transplant).
#
# WHY v3 (vs v2): v2 was rank 64 / alpha 128 / 4 epochs / LR 2e-4 — far too much capacity + too
# many epochs for a *voice* adapter on a 27B base. It overwrote reasoning, not just tone, which is
# why v2 only worked with the LoRA weight dialed to ~0.6 and fell into memorized grooves (the loop).
# v3 = rank 16 / alpha 32 (2:1 kept) / 2 epochs / LR 1e-4. Goal: coherent AND in-character at
# weight 1.0. If it needs dilution to be usable, it's still over-trained.
# Dataset also reworked: v2's 108 single-turns (kept) + multi-turn conversations + autonomy-
# continuation (existence/deciding, NOT task-seeking) + register variety. See v3 build plan.
#
# Run:  python train_nova_lora_v3.py   (after building nova_core_v3.jsonl — see RUNBOOK)
# Base is FROZEN, bf16, no quantization — only the LoRA learns.

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# ── Config ──────────────────────────────────────────────────────────────────
# MUST match the base the live GGUF was converted from, or the adapter won't apply cleanly
# when KoELS equips it. VERIFY this repo id before a full run (v3 build plan, gate #1).
MODEL_ID   = "unsloth/Qwen3.6-27B"
DATA_PATH  = "nova_core_v3.jsonl"      # v2 108 + multi-turn + autonomy-continuation + register
OUTPUT_DIR = "nova_core_v3_out"

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

# ── LoRA: voice/style across attention + MLP, LOW rank so it can't overwrite reasoning ──
peft_cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none",   # v3: half v2's rank, quarter its alpha
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

# ── Data: TRL applies Qwen's chat template to the {"messages":[...]} rows ────
ds = load_dataset("json", data_files=DATA_PATH, split="train")

cfg_kwargs = dict(
    output_dir=OUTPUT_DIR,
    num_train_epochs=2,                   # v3: FEWER epochs. Save per epoch, A/B 1 vs 2 at weight 1.0.
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,        # effective batch 8
    learning_rate=1e-4,                   # v3: halved from 2e-4 — gentler imprint
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    max_length=4096,                      # v3: raised from 2048 — multi-turn + autonomy wakes are
                                          #     longer; at 2048 they'd silently truncate mid-example.
    packing=False,                        # keep example boundaries crisp for voice
    logging_steps=5,
    save_strategy="epoch",
    optim="adamw_torch",
    report_to="none",
    seed=42,
)

# ── Loss masking (v3 fix): train on Nova's turns ONLY, if the stack supports it. ────────────
# The autonomy examples carry long user-side wake boilerplate; with default full-sequence loss
# those tokens dominate and teach her to EMIT wake-prompt text. assistant_only_loss masks them.
# TRL requires a chat template with {% generation %} support — Qwen's may not have it — so we
# PROBE one batch and fall back to full-sequence loss (exact v2 behavior) instead of dying.
# Escape hatch: NOVA_ASSISTANT_ONLY=0 forces the v2 behavior.
# NOTE for the runbook: if the first logged train loss is ~0.0, the mask is degenerate —
# rerun with NOVA_ASSISTANT_ONLY=0.
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
        print("[v3] assistant_only_loss=True — loss restricted to Nova's turns.")
    except Exception as e:
        print(f"[v3] assistant_only_loss unsupported here ({type(e).__name__}: {str(e)[:200]}) "
              f"— falling back to full-sequence loss (v2 behavior).")
        trainer = None
if trainer is None:
    trainer = _build_trainer(assistant_only=False)

if __name__ == "__main__":
    trainer.train()
