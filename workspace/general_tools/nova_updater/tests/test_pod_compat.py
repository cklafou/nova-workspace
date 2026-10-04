# Last updated: 2026-10-04 14:04:43
# @nova: Verify conditional-model loader selection, assistant masking, language-only LoRA and a disposable tiny training checkpoint.
import importlib.util
import os
from pathlib import Path
import tempfile
import sys
import types
import unittest

from nova_updater.pod import train_lora, template_gen


class PodContracts(unittest.TestCase):
    def test_loader_matches_full_qwen_config(self):
        loaders = types.SimpleNamespace(Qwen3_5ForConditionalGeneration=object(), AutoModelForCausalLM=object())
        full = types.SimpleNamespace(model_type="qwen3_5", architectures=["Qwen3_5ForConditionalGeneration"])
        self.assertIs(train_lora.model_loader(full, loaders), loaders.Qwen3_5ForConditionalGeneration)
        self.assertIs(train_lora.model_loader(types.SimpleNamespace(model_type="qwen3"), loaders), loaders.AutoModelForCausalLM)
        for config in (types.SimpleNamespace(model_type="other", vision_config={}),
                       types.SimpleNamespace(model_type="qwen3_5", architectures=["WrongClass"])):
            with self.assertRaises(ValueError):
                train_lora.model_loader(config, loaders)

    def test_data_audit_rejects_lost_assistant_and_vision_rows(self):
        tok = types.SimpleNamespace(apply_chat_template=lambda *a, **k:
                                   {"input_ids": [1, 2, 3, 4, 5], "assistant_masks": [0, 0, 0, 1, 1]})
        rows = [{"messages": [{"role": "assistant", "content": "answer"}]}]
        self.assertEqual(train_lora.audit_rows(tok, rows, 4),
                         {"rows": 1, "max_tokens": 5, "truncated_rows": 1,
                          "assistant_tokens": 1, "min_assistant_tokens": 1})
        for data, length in ((rows, 3), ([], 4), ([dict(rows[0], images=[])], 4),
                             ([{"messages": [{"content": [{"type": "image"}]}]}], 4)):
            with self.assertRaises(ValueError):
                train_lora.audit_rows(tok, data, length)


    def test_run_details_receipt_is_bounded_and_separately_checksummed(self):
        import hashlib
        import re
        shell = (Path(train_lora.__file__).parent / "run_on_pod.sh").read_text(encoding="utf-8")
        receipt = shell.split("# Bounded reproducibility receipt", 1)[1]
        script = re.search(r"python3 - <<'EOF'\n(.*?)\nEOF", receipt, re.S).group(1)
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                for name in ("environment.txt", "base_source.json", "tokenization_report.json",
                             "chat_template.gen.jinja", "base_config/config.json"):
                    target = Path(name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("fixture", encoding="utf-8")
                Path("secret-not-for-receipt.txt").write_text("excluded")
                exec(compile(script, "pod-run-details", "exec"), {})
                output = Path("gguf_out/training_details")
                manifest = (output / "SHA256SUMS.txt").read_text().splitlines()
                self.assertEqual(len(manifest), 6)
                for line in manifest:
                    digest, name = line.split("  ", 1)
                    self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
                self.assertFalse((output / "secret-not-for-receipt.txt").exists())
                self.assertFalse(Path("gguf_out/SHA256SUMS.txt").exists())
            finally:
                os.chdir(previous)


@unittest.skipUnless(os.environ.get("NOVA_POD_COMPAT_TEST") == "1",
                     "opt-in CPU proof needs the isolated pinned pod dependencies; never downloads weights")
class TinyTraining(unittest.TestCase):
    def test_qwen_conditional_text_only_sft_checkpoint(self):
        import torch
        from datasets import Dataset
        from tokenizers import Tokenizer, models, pre_tokenizers, decoders
        from transformers import PreTrainedTokenizerFast, Qwen3_5Config, Qwen3_5ForConditionalGeneration
        chars = sorted(set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_[]<>|/.,:'!?\n -"))
        vocab = {ch: i for i, ch in enumerate(chars)}
        vocab.update({"[UNK]": len(vocab), "<|im_end|>": len(vocab) + 1, "[PAD]": len(vocab) + 2})
        base = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
        base.pre_tokenizer = pre_tokenizers.Split("", "isolated")
        base.decoder = decoders.Fuse()
        tok = PreTrainedTokenizerFast(tokenizer_object=base, unk_token="[UNK]", eos_token="<|im_end|>", pad_token="[PAD]")
        official = (Path(__file__).parent / "fixtures/qwen3.8-27b.chat_template.jinja").read_text(encoding="utf-8")
        template_gen.gates(tok, official, template_gen.mark(official))
        cfg = Qwen3_5Config(
            text_config=dict(vocab_size=128, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                             num_attention_heads=2, num_key_value_heads=1, head_dim=16,
                             linear_num_key_heads=1, linear_num_value_heads=2, linear_key_head_dim=16,
                             linear_value_head_dim=16, mtp_num_hidden_layers=1, layer_types=["linear_attention", "full_attention"],
                             max_position_embeddings=2048, rope_parameters={"rope_type": "default", "rope_theta": 10000.0,
                             "partial_rotary_factor": 1.0, "mrope_section": [2, 3, 3]}),
            vision_config=dict(depth=1, hidden_size=32, intermediate_size=64, num_heads=2, out_hidden_size=32,
                               patch_size=2, spatial_merge_size=1, temporal_patch_size=1, num_position_embeddings=16),
            image_token_id=125, video_token_id=126, vision_start_token_id=127)
        cfg.architectures = ["Qwen3_5ForConditionalGeneration"]
        model = Qwen3_5ForConditionalGeneration(cfg)
        before = {name: parameter.detach().clone() for name, parameter in model.model.visual.named_parameters()}
        rows = Dataset.from_list([{"messages": [{"role": "user", "content": "USER_ONLY_SENTINEL"},
                                               {"role": "assistant", "content": "Hey."}]}])
        params = dict(r=2, alpha=4, dropout=0.05, epochs=1, lr=1e-4, batch=1, grad_accum=1,
                      max_length=512, scheduler="cosine", warmup_ratio=0.0, seed=42,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        self.assertGreater(train_lora.audit_rows(tok, rows, 512)["assistant_tokens"], 0)
        with tempfile.TemporaryDirectory(prefix="nova-tiny-qwen-") as folder:
            trainer = train_lora.make_trainer(model, tok, rows, params, folder, cpu=True)
            batch = trainer.data_collator([trainer.train_dataset[0]])
            labels = batch["labels"][0]
            kept = tok.decode(batch["input_ids"][0][labels != -100])
            self.assertIn("Hey.", kept)
            self.assertNotIn("USER_ONLY_SENTINEL", kept)
            outcome = trainer.train()
            self.assertTrue(torch.isfinite(torch.tensor(outcome.training_loss)))
            checkpoint = Path(folder) / "checkpoint-1"
            self.assertTrue((checkpoint / "adapter_model.safetensors").is_file())
            from safetensors.torch import load_file
            adapter = load_file(str(checkpoint / "adapter_model.safetensors"))
            self.assertTrue(adapter)
            self.assertTrue(all(".language_model." in key for key in adapter))
            self.assertTrue(any(tensor.abs().sum() > 0 for key, tensor in adapter.items() if ".lora_B." in key))
            self.assertTrue(all(torch.equal(before[name], parameter) for name, parameter in model.model.visual.named_parameters()))
            converter = os.environ.get("NOVA_POD_CONVERTER")
            if converter:
                import subprocess
                cfg.save_pretrained(Path(folder) / "base_config")
                converted = Path(folder) / "tiny.gguf"
                env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
                completed = subprocess.run([sys.executable, str(Path(converter) / "convert_lora_to_gguf.py"),
                    str(checkpoint), "--base", str(Path(folder) / "base_config"), "--outfile", str(converted)],
                    env=env, capture_output=True, text=True, timeout=60)
                self.assertEqual(completed.returncode, 0, completed.stderr[-2500:])
                self.assertEqual(converted.read_bytes()[:4], b"GGUF")
            # Optional evidence copy for running the pinned converter against this tiny adapter.
            destination = os.environ.get("NOVA_POD_COMPAT_OUTPUT")
            if destination:
                import shutil
                shutil.copytree(checkpoint, Path(destination) / "checkpoint-1", dirs_exist_ok=True)
                cfg.save_pretrained(Path(destination) / "base_config")


if __name__ == "__main__":
    unittest.main()
