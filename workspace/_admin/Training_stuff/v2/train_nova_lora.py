#!/usr/bin/env python3
# Last updated: 2026-06-22 11:58:19
"""
Nova-Core personality LoRA — bf16 training on Qwen 3.6 27B.
Target: a single A100/H100 80GB (Vertex AI Workbench or Custom Job).

This trains a *style/voice* adapter, NOT facts. Keep epochs low; over-training a
personality LoRA degrades the base model's intelligence. The base is FROZEN and
loaded in bf16 (no quantization) — only the LoRA adapter learns.

Run:  python train_nova_lora.py
Deps: see TRAIN_ON_VERTEX.md (transformers, peft, trl, accelerate, datasets).
"""
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# ── Config ──────────────────────────────────────────────────────────────────
# IMPORTANT: this MUST be the SAME base your GGUF was quantized from, or the
# adapter won't apply cleanly when KoELS equips it. Confirm the exact repo id.
MODEL_ID   = "unsloth/Qwen3.6-27B"        # the safetensors base the Q6_K_XL GGUF was made from (v1 trained+converted cleanly off this)
DATA_PATH  = "nova_core_v2.jsonl"       # 108 conversational examples (v2, with-teeth dataset)
OUTPUT_DIR = "nova_core_v2_out"            # adapter lands here

# ── Tokenizer + base model (bf16, frozen) ───────────────────────────────────
tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,           # no quantization — full bf16 base
    device_map="auto",
    trust_remote_code=True,
    attn_implementation="sdpa",           # swap to "flash_attention_2" if installed
)
model.config.use_cache = False            # required with gradient checkpointing

# ── LoRA: voice/style across all attention + MLP projections ────────────────
peft_cfg = LoraConfig(
    r=64, lora_alpha=128, lora_dropout=0.05, bias="none",   # v2: doubled rank for personality headroom (alpha/r=2 kept)
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

# ── Data: TRL applies Qwen's chat template to the {"messages":[...]} rows ────
ds = load_dataset("json", data_files=DATA_PATH, split="train")

cfg = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=4,                   # 108 examples → train a bit longer for a deep imprint; save per epoch and A/B 2/3/4 to find strongest-before-overfit
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,        # effective batch 8
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    max_length=2048,                      # (SFTConfig uses max_length, NOT max_seq_length — that errored last run)
    packing=False,                        # keep example boundaries crisp for voice
    logging_steps=5,
    save_strategy="epoch",
    optim="adamw_torch",
    report_to="none",
    seed=42,
)

trainer = SFTTrainer(
    model=model,
    args=cfg,
    train_dataset=ds,
    peft_config=peft_cfg,
    processing_class=tok,
)

if __name__ == "__main__":
    t