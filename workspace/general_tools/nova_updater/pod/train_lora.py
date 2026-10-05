# Last updated: 2026-10-06 03:19:20
# @nova: Train text-only assistant-masked LoRA with an architecture-matched loader and frozen vision layers.
"""GPU-pod entry point; importing this module never downloads or loads a model.

Qwen3.8's full config is qwen3_5 / Qwen3_5ForConditionalGeneration. Keep that
wrapper and its parameter names for GGUF conversion, while training only the
reviewed language-layer targets. TRL receives a tokenizer and text-only rows.
"""
import json
from pathlib import Path
import sys


def model_loader(config, transformers):
    if config.model_type == "qwen3_5":
        if config.architectures != ["Qwen3_5ForConditionalGeneration"]:
            raise ValueError("Unsupported qwen3_5 architecture; refusing to guess a loader")
        return transformers.Qwen3_5ForConditionalGeneration
    if getattr(config, "vision_config", None) is not None:
        raise ValueError("This multimodal architecture has not been validated for text-only training")
    return transformers.AutoModelForCausalLM


def language_targets(model, requested):
    """Resolve exact linear-module names; suffix matches must never train vision."""
    import torch
    composite = model.config.model_type == "qwen3_5"
    selected = [name for name, module in model.named_modules()
                if isinstance(module, torch.nn.Linear)
                and name.rsplit(".", 1)[-1] in requested
                and (not composite or name.startswith("model.language_model."))]
    missing = set(requested) - {name.rsplit(".", 1)[-1] for name in selected}
    if missing or not selected:
        raise ValueError(f"Reviewed LoRA target modules not found in language model: {sorted(missing)}")
    return selected


def audit_rows(tok, rows, max_length):
    """Fail before weights load if any text row loses all assistant labels."""
    lengths, trained, truncated = [], [], 0
    for number, row in enumerate(rows, 1):
        if any(key in row for key in ("image", "images", "video", "videos")):
            raise ValueError(f"Row {number}: only text training is supported")
        messages = row.get("messages", [])
        if any(not isinstance(message.get("content", ""), str) for message in messages):
            raise ValueError(f"Row {number}: multimodal message content is unsupported")
        enc = tok.apply_chat_template(messages, tokenize=True, return_dict=True,
                                      return_assistant_tokens_mask=True,
                                      **({"tools": row["tools"]} if row.get("tools") else {}))
        ids, mask = enc["input_ids"], enc["assistant_masks"]
        if len(ids) != len(mask) or not any(mask[1:max_length]):
            raise ValueError(f"Row {number}: no assistant loss survives max_length={max_length}")
        lengths.append(len(ids))
        trained.append(sum(mask[1:max_length]))
        truncated += len(ids) > max_length
    if not lengths:
        raise ValueError("Empty training dataset")
    return {"rows": len(lengths), "max_tokens": max(lengths), "truncated_rows": truncated,
            "assistant_tokens": sum(trained), "min_assistant_tokens": min(trained)}


def make_trainer(model, tok, rows, params, output_dir, *, cpu=False):
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer
    targets = language_targets(model, params["target_modules"])
    model.config.use_cache = False
    if hasattr(model.config, "text_config"):
        model.config.text_config.use_cache = False
    # PEFT freezes the base; exact language targets keep vision and projector frozen.
    peft_cfg = LoraConfig(r=int(params["r"]), lora_alpha=int(params["alpha"]),
                         lora_dropout=float(params["dropout"]), bias="none",
                         task_type="CAUSAL_LM", target_modules=targets)
    args = SFTConfig(
        output_dir=str(output_dir), num_train_epochs=float(params["epochs"]),
        per_device_train_batch_size=int(params["batch"]),
        gradient_accumulation_steps=int(params["grad_accum"]), learning_rate=float(params["lr"]),
        lr_scheduler_type=params.get("scheduler", "cosine"),
        warmup_steps=float(params.get("warmup_ratio", 0.03)), bf16=not cpu, use_cpu=cpu,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=int(params["max_length"]), packing=False, logging_steps=5,
        save_strategy="epoch", optim="adamw_torch", report_to="none",
        seed=int(params.get("seed", 42)), assistant_only_loss=True,
        loss_type="nll",  # explicit: do not apply TRL's version-dependent chunked-head patch
        dataset_num_proc=None, dataloader_num_workers=0, dataloader_pin_memory=not cpu,
    )
    trainer = SFTTrainer(model=model, args=args, train_dataset=rows,
                         peft_config=peft_cfg, processing_class=tok)
    if len(trainer.train_dataset) != len(rows):
        raise ValueError("Trainer dropped rows from the reviewed dataset")
    if any(not any(label != -100 for label in row["labels"][1:]) for row in trainer.train_dataset):
        raise ValueError("Trainer produced a row without assistant loss")
    trained = [name for name, parameter in trainer.model.named_parameters() if parameter.requires_grad]
    if not trained or (model.config.model_type == "qwen3_5" and
                       any(".language_model." not in name or "lora_" not in name for name in trained)):
        raise ValueError("Training escaped the reviewed language-only LoRA targets")
    return trainer


def main(argv=None):
    import torch
    import transformers
    from datasets import load_dataset
    from packaging.version import Version
    from template_gen import gates
    argv = argv or sys.argv[1:]
    job = json.loads(Path(argv[0] if argv else "job.json").read_text(encoding="utf-8"))
    params, model_id = job["params"], job["base_model_id"]
    if Version(torch.__version__.split("+")[0]) < Version("2.6"):
        raise RuntimeError("The pod image must provide CUDA PyTorch >=2.6; no automatic Torch replacement")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Training requires one CUDA GPU with bf16 support")
    source = json.loads(Path("base_source.json").read_text(encoding="utf-8"))
    if source["model_id"] != model_id or not source.get("revision"):
        raise ValueError("Missing or mismatched pinned base metadata; run template_gen.py first")
    revision = source["revision"]
    config = transformers.AutoConfig.from_pretrained(model_id, revision=revision, trust_remote_code=False)
    loader = model_loader(config, transformers)
    tok = transformers.AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    official = tok.chat_template
    marked = Path(job.get("template_file", "chat_template.gen.jinja")).read_text(encoding="utf-8")
    print("[train]", gates(tok, official, marked))
    rows = load_dataset("json", data_files=[item["name"] for item in job["data"]], split="train")
    expected = sum(int(item["rows"]) for item in job["data"])
    if len(rows) != expected:
        raise ValueError(f"Dataset rows {len(rows)} != reviewed {expected}")
    audit = audit_rows(tok, rows, int(params["max_length"]))
    Path("tokenization_report.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print("[train] reviewed dataset:", audit)
    # Single-device training; fail on insufficient VRAM instead of inference-only CPU offloading.
    model = loader.from_pretrained(model_id, revision=revision, config=config,
                                   dtype=torch.bfloat16, device_map={"": 0},
                                   trust_remote_code=False, attn_implementation="sdpa")
    trainer = make_trainer(model, tok, rows, params, job.get("output_dir", "lora_out"))
    trainer.train()
    print("[train] TRAINING COMPLETE")


if __name__ == "__main__":
    main()
