# Last updated: 2026-10-05 21:27:11
# @nova: Prove KoELS preload arguments survive the real Windows launcher and current llama parser without loading models.
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "nova_body/nova_runtime/koels_equip.py"
LAUNCHER = WORKSPACE / "start_llama_qwen36.cmd"
PARSER = WORKSPACE / "llama/llama-server.exe"


def pure_builders():
    # Execute the real pure methods without importing Nova's runtime or personal state.
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "KoELSEquip")
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name in {"build_lora_args", "build_lora_args_line"}]
    namespace = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["KoELSEquip"]


class KoELSArgumentTests(unittest.TestCase):
    def test_empty_loadout_adds_no_flags(self):
        equip = pure_builders()
        for empty in (None, []):
            self.assertEqual(equip.build_lora_args(empty), [])
            self.assertEqual(equip.build_lora_args_line(empty), "")

    def test_single_adapter_is_one_path_scale_argument(self):
        equip = pure_builders()
        path = r"models\fixture\specialist.gguf"
        self.assertEqual(equip.build_lora_args([path]),
                         ["--lora-scaled", path + ":0.0", "--lora-init-without-apply"])
        self.assertEqual(equip.build_lora_args_line([path]),
                         f'--lora-scaled "{path}:0.0" --lora-init-without-apply')

    def test_multiple_adapters_keep_each_scale_attached(self):
        equip = pure_builders()
        paths = [r"models\fixture\first.gguf", r"models\fixture folder\second.gguf"]
        self.assertEqual(equip.build_lora_args(paths),
                         ["--lora-scaled", paths[0] + ":0.0", "--lora-scaled", paths[1] + ":0.0",
                          "--lora-init-without-apply"])


@unittest.skipUnless(os.name == "nt" and PARSER.is_file(), "needs the installed Windows llama parser")
class KoELSLauncherTests(unittest.TestCase):
    def test_generated_batch_line_preserves_personality_and_multiple_specialists(self):
        equip = pure_builders()
        specialists = [r"models\fixture\first.gguf", r"models\fixture folder\second.gguf"]
        with tempfile.TemporaryDirectory(prefix="nova-koels-launcher-") as tmp:
            root = Path(tmp)
            launcher = LAUNCHER.read_text(encoding="utf-8")
            marker = ".\\llama\\llama-server.exe ^"
            self.assertEqual(launcher.count(marker), 1)
            launcher = launcher.replace(marker, f'"{sys.executable}" capture.py ^')
            launcher = launcher.replace("\npause", "\nexit /b 0")
            (root / "launch.cmd").write_bytes(launcher.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
            (root / "capture.py").write_text(
                "import json,sys\nfrom pathlib import Path\nPath('args.json').write_text(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8")
            memory = root / "nova_body/memory"
            memory.mkdir(parents=True)
            core = r"models\fixture\personality.gguf:0.7"
            for name, value in {"active_model.txt": r"models\fixture\model.gguf",
                                "active_mmproj.txt": "none", "active_lora.txt": "--lora-scaled " + core,
                                "koels_lora_args.txt": equip.build_lora_args_line(specialists)}.items():
                (memory / name).write_bytes(value.encode("ascii") + b"\r\n")
            result = subprocess.run(["cmd", "/d", "/c", "launch.cmd"], cwd=root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace",
                                    timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            argv = json.loads((root / "args.json").read_text())
            scaled = [argv[i + 1] for i, token in enumerate(argv) if token == "--lora-scaled"]
            self.assertEqual(scaled, [core, *(path + ":0.0" for path in specialists)])
            self.assertEqual(argv.count("--lora-init-without-apply"), 1)
            # --help parses these exact arguments and exits before reading any model or adapter.
            parsed = subprocess.run([str(PARSER), *argv, "--help"], cwd=root, capture_output=True,
                                    text=True, errors="replace", timeout=15,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(parsed.returncode, 0, parsed.stderr)
            self.assertIn("--lora-scaled FNAME:SCALE", parsed.stdout + parsed.stderr)

    def test_installed_parser_rejects_the_previous_separate_scale_format(self):
        with tempfile.TemporaryDirectory(prefix="nova-koels-parser-") as tmp:
            result = subprocess.run([str(PARSER), "--lora-scaled", "fixture.gguf", "0.0", "--help"],
                                    cwd=tmp, capture_output=True, text=True, errors="replace", timeout=15,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lora-scaled format: FNAME:SCALE", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
