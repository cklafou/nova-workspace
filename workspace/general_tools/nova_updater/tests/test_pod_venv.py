# Last updated: 2026-10-05 18:20:08
# @nova: Prove the pod bootstrap installs dependencies in a venv while retaining the image Python packages.
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


@unittest.skipUnless(os.name == "posix", "Linux pod bootstrap smoke; run through WSL on Windows")
class PodEnvironment(unittest.TestCase):
    def test_default_is_local_and_job_keys_are_separate_and_repeatable(self):
        shell = (Path(__file__).parents[1] / "pod/run_on_pod.sh").read_text(encoding="utf-8")
        selector = re.search(r"TRAIN_VENV=\$\(python3 - <<'EOF'\n(.*?)\nEOF\n\)", shell, re.S).group(1)
        env = dict(os.environ)
        env.pop("NOVA_TRAINING_CACHE_DIR", None)
        with tempfile.TemporaryDirectory(prefix="nova-pod-keys-") as folder:
            root = Path(folder)
            first, second = root / "job-a", root / "job-b"
            for job in (first, second):
                job.mkdir()
                (job / "job.json").write_text('{"same": "recipe"}')
            def selected(job):
                result = subprocess.run(["python3", "-c", selector], cwd=job, env=env,
                                        capture_output=True, text=True, check=True)
                return Path(result.stdout.strip())
            initial = selected(first)
            self.assertEqual(initial.parent, Path("/root/.cache/nova-training"))
            self.assertRegex(initial.name, r"^[0-9a-f]{24}$")
            self.assertEqual(selected(first), initial)
            self.assertNotEqual(selected(second), initial)
            (first / "job.json").write_text('{"changed": "recipe"}')
            self.assertNotEqual(selected(first), initial)

    def test_real_bootstrap_and_offline_install_stay_inside_venv(self):
        shell = (Path(__file__).parents[1] / "pod/run_on_pod.sh").read_text(encoding="utf-8")
        bootstrap = shell.split("# BEGIN TRAINING VENV\n", 1)[1].split("# END TRAINING VENV", 1)[0]
        with tempfile.TemporaryDirectory(prefix="nova-pod-env-") as folder:
            container = Path(folder)
            root = container / "network-volume" / "job"
            root.mkdir(parents=True)
            (root / "job.json").write_text('{"job": "one"}')
            cache = container / "container-local-cache"
            env = dict(os.environ, NOVA_TRAINING_CACHE_DIR=str(cache))
            wheel = root / "nova_pod_env_probe-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("nova_pod_env_probe/__init__.py", "VALUE = 42\n")
                archive.writestr("nova_pod_env_probe-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: nova-pod-env-probe\nVersion: 1.0\n")
                archive.writestr("nova_pod_env_probe-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: nova-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                archive.writestr("nova_pod_env_probe-1.0.dist-info/RECORD", "")
            probe = root / "probe.py"
            probe.write_text("import json,sys,nova_pod_env_probe,pip\nfrom pathlib import Path\n"
                             "print(json.dumps(dict(prefix=sys.prefix,base=sys.base_prefix,"
                             "module=nova_pod_env_probe.__file__,pip=pip.__file__,value=nova_pod_env_probe.VALUE)))\n")
            script = "set -euo pipefail\n" + bootstrap + "\npython3 -m pip install --no-index --no-deps --disable-pip-version-check " + wheel.name + "\npython3 probe.py > result.json\n"
            result = subprocess.run(["bash", "-c", script], cwd=root, env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = json.loads((root / "result.json").read_text())
            venv = Path(output["prefix"])
            self.assertEqual(venv.parent, cache)
            self.assertFalse(venv.is_relative_to(root))
            self.assertNotEqual(output["prefix"], output["base"])
            self.assertTrue(Path(output["module"]).is_relative_to(venv))
            self.assertFalse(Path(output["pip"]).is_relative_to(venv))  # inherited, not bootstrapped
            self.assertEqual(output["value"], 42)
            config = (venv / "pyvenv.cfg").read_text()
            self.assertIn("include-system-site-packages = true", config)
            outside = subprocess.run(["python3", "-c", "import importlib.util; assert importlib.util.find_spec('nova_pod_env_probe') is None"], capture_output=True, text=True)
            self.assertEqual(outside.returncode, 0, outside.stderr)


if __name__ == "__main__":
    unittest.main()
