# @nova: Runs the real model launcher on Windows with llama-server swapped for an argument recorder, proving boot files reach llama-server intact.
"""Windows only (needs cmd.exe); skipped elsewhere. No model file is read and nothing is started.

Run: python -m unittest discover -s general_tools/nova_updater/tests -v
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

LAUNCHER = Path(__file__).resolve().parents[3] / "start_llama_qwen36.cmd"
SERVER_LINE = ".\\llama\\llama-server.exe ^"
DEFAULT_MODEL = "models\\qwen3.6\\Qwen3.6-27B-UD-Q6_K_XL.gguf"
DEFAULT_MMPROJ = "models\\qwen3.6\\mmproj-F16.gguf"
V2_ADAPTER = "models\\qwen3.6\\nova_core_v2_e2.gguf"


@unittest.skipUnless(os.name == "nt" and LAUNCHER.is_file(), "needs Windows cmd.exe and the real launcher")
class Launcher(unittest.TestCase):
    def launch(self, boot=None, files=()):
        """Copy the launcher into a throwaway folder, swap llama-server for a recorder, run it, return argv."""
        root = Path(tempfile.mkdtemp(prefix="nova-launcher-"))
        self.addCleanup(shutil.rmtree, root, True)
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn(SERVER_LINE, text, "the launcher's llama-server line changed; update this test")
        text = text.replace(SERVER_LINE, f'"{sys.executable}" capture.py ^').replace("\npause", "\nexit /b 0")
        (root / "launch.cmd").write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        (root / "capture.py").write_text(
            "import json, sys\nopen('args.json', 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))\n")
        memory = root / "nova_body" / "memory"
        memory.mkdir(parents=True)
        for name, value in (boot or {}).items():
            (memory / name).write_bytes(value.encode("ascii") + b"\r\n")
        for rel in files:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(b"")
        done = subprocess.run(["cmd", "/d", "/c", "launch.cmd"], cwd=root, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, errors="replace", timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads((root / "args.json").read_text(encoding="utf-8"))

    @staticmethod
    def after(args, flag):
        return args[args.index(flag) + 1] if flag in args else None

    def test_defaults_without_boot_files(self):
        args = self.launch()
        self.assertEqual((self.after(args, "-m"), self.after(args, "--mmproj")), (DEFAULT_MODEL, DEFAULT_MMPROJ))
        self.assertNotIn("--lora-scaled", args)

    def test_paths_with_spaces_stay_one_argument(self):
        model, proj = "models\\custom folder\\model.gguf", "models\\custom folder\\mmproj-F16.gguf"
        args = self.launch({"active_model.txt": model, "active_mmproj.txt": proj})
        self.assertEqual((self.after(args, "-m"), self.after(args, "--mmproj")), (model, proj))
        self.assertEqual(args[-2:], ["--mmproj", proj])


    def test_complete_adapter_token_with_spaces_is_one_argument(self):
        adapter = "models\\Qwen 3.8 27B Dense\\Nova Personality Epoch 2.gguf"
        args = self.launch({"active_lora.txt": f'--lora-scaled "{adapter}:0.6"'})
        self.assertEqual(self.after(args, "--lora-scaled"), adapter + ":0.6")
        self.assertNotIn('Epoch', args)

    def test_quotes_inside_boot_files_do_not_double_up(self):
        args = self.launch({"active_model.txt": '"models\\q x\\m.gguf"', "active_mmproj.txt": '"models\\q x\\p.gguf"'})
        self.assertEqual((self.after(args, "-m"), self.after(args, "--mmproj")), ("models\\q x\\m.gguf", "models\\q x\\p.gguf"))

    def test_none_means_no_vision(self):
        self.assertNotIn("--mmproj", self.launch({"active_mmproj.txt": "none"}))

    def test_adapter_line_and_the_v2_fallback(self):
        self.assertEqual(self.after(self.launch(files=[V2_ADAPTER]), "--lora-scaled"), V2_ADAPTER + ":0.6")
        custom = self.launch({"active_model.txt": "models\\qwen3.8\\m.gguf"}, files=[V2_ADAPTER])
        self.assertNotIn("--lora-scaled", custom)  # the v2 adapter belongs to Qwen 3.6 only
        line = self.launch({"active_lora.txt": "--lora-scaled models\\qwen3.8\\a.gguf:0.8"})
        self.assertEqual(self.after(line, "--lora-scaled"), "models\\qwen3.8\\a.gguf:0.8")
        self.assertNotIn("--lora-scaled", self.launch({"active_lora.txt": "none"}, files=[V2_ADAPTER]))


if __name__ == "__main__":
    unittest.main()
