# @nova: Trains one LoRA on the pod from job.json, keeping v7's proven recipe and its hard mask gate; generalised for any base model.
"""Generic LoRA trainer (runs ON the GPU pod).

Same recipe as Nova-core v5-v7 (TRL SFTTrainer, PEFT LoRA, bf16, assistant-only loss), with the
model id, data files and hyperparameters read from job.json instead of hard-coded. The chat
template comes from template_gen.py, which has already proven the mask (GATE A/B); the mask is
proven AGAIN here, every run, because training on user/tool text teaches the model to fabricate
its own evidence. There is no fallback path: if the mask breaks, the run dies.
"""
import json
import os
import sys

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

JOB = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "job.json", encoding="utf-8"))
P = JOB["params"]
MODEL_ID = JOB["base_model_id"]
OUTPUT_DIR = JOB.get("output_dir", "lora_out")
DATA = [d["name"] for d in JOB["data"]]

tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
with open(JOB.get("template_file", "chat_template.gen.jinja"), encoding="utf-8") as fh:
    tok.chat_template = fh.read()
assert "generation %}" in tok.chat_template, "template missing generation markers"

_c = [{"role": "user", "content": "USER_TEXT_MUST_BE_MASKED"},
      {"role": "assistant", "content": "ASSISTANT_TEXT_MUST_BE_TRAINED"}]
_o = tok.apply_chat_template(_c, tokenize=True, return_dict=True, return_assistant_tokens_mask=True)
_ids, _mask = _o["input_ids"], _o["assistant_masks"]
if _mask and isinstance(_mask[0], list):
    _ids, _mask = _ids[0], _mask[0]
_t = tok.decode([i for i, k in zip(_ids, _mask) if k == 1])
assert "ASSISTANT_TEXT_MUST_BE_TRAINED" in _t, "MASK BROKEN: assistant turns are not being trained"
assert "USER_TEXT_MUST_BE_MASKED" not in _t, "MASK BROKEN: user/tool text would be trained. REFUSING TO TRAIN."
print("[train] mask verified - loss on assistant turns only:", repr(_t))

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
    trust_remote_code=True, attn_implementation="sdpa",
)
model.config.use_cache = False

peft_cfg = LoraConfig(r=int(P["r"]), lora_alpha=int(P["alpha"]), lora_dropout=float(P["dropout"]),
                      bias="none", task_type="CAUSAL_LM", target_modules=list(P["target_modules"]))

ds = load_dataset("json", data_files=DATA, split="train")
print(f"[train] dataset rows: {len(ds)} from {len(DATA)} file(s); base {MODEL_ID}")
expected = sum(int(d["rows"]) for d in JOB["data"])
assert len(ds) == expected, f"row count {len(ds)} != reviewed {expected}"

args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=float(P["epochs"]),
    per_device_train_batch_size=int(P["batch"]),
    gradient_accumulation_steps=int(P["grad_accum"]),
    learning_rate=float(P["lr"]),
    lr_scheduler_type=P.get("scheduler", "cosine"),
    warmup_ratio=float(P.get("warmup_ratio", 0.03)),
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    max_length=int(P["max_length"]),
    packing=False,
    logging_steps=5,
    save_strategy="epoch",
    optim="adamw_torch",
    report_to="none",
    seed=int(P.get("seed", 42)),
    assistant_only_loss=True,
)

trainer = SFTTrainer(model=model, args=args, train_dataset=ds, peft_config=peft_cfg, processing_class=tok)

if __name__ == "__main__":
    trainer.train()
    print("[train] TRAINING COMPLETE")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
