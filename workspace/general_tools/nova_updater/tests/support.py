# @nova: Test helpers for the updater: a throwaway workspace (launcher, boot files, fake models) and fake catalogs, so tests never touch real models or the network.
"""Shared fixtures. Every test runs inside a temporary workspace set through environment variables."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # general_tools/

from nova_updater import catalog, check, gguf, net  # noqa: E402

LAUNCHER = (
    "@echo off\r\n"
    'set "NOVA_MODEL=models\\qwen3.6\\Qwen3.6-27B-UD-Q6_K_XL.gguf"\r\n'
    'set "NOVA_MMPROJ=models\\qwen3.6\\mmproj-F16.gguf"\r\n'
    '.\\llama\\llama-server.exe ^\r\n    -m "%NOVA_MODEL%" ^\r\n    --port 8080 %NOVA_VISION%\r\n'
)


class Workspace(unittest.TestCase):
    """Base class: temp workspace with today's Qwen 3.6 setup."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        (self.ws / "nova_body" / "memory").mkdir(parents=True)
        (self.ws / "models" / "qwen3.6").mkdir(parents=True)
        (self.ws / "start_llama_qwen36.cmd").write_text(LAUNCHER, encoding="utf-8", newline="")
        env = {"NOVA_WORKSPACE": str(self.ws), "NOVA_UPDATER_STATE": str(self.ws / "state"),
               "NOVA_UPDATER_CREDENTIALS": str(self.ws / "creds" / "credentials.json")}
        for name in ("NOVA_MODELS_DIR", "NOVA_BODY", "NOVA_LAUNCHER", "NOVA_TRASH_DIR", "NOVA_UPDATER_WORK"):
            env.setdefault(name, "")
        self._old = {k: os.environ.get(k) for k in env}
        for key, value in env.items():
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
        self.addCleanup(self._restore_env)
        check._session_declined.clear()

    def _restore_env(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def model_file(self, rel, kv=None):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        gguf.write_minimal(path, kv or {"general.architecture": "qwen35", "general.name": "Qwen3.6 27B",
                                        "general.basename": "Qwen3.6", "general.size_label": "27B"})
        return path

    def boot(self, name, text):
        (self.ws / "nova_body" / "memory" / name).write_text(text, encoding="utf-8", newline="")


def hit(model_id, params=None, license="apache-2.0", pipeline="image-text-to-text", created="2026-08-05T00:00:00Z",
        formats=None, downloads=0):
    return catalog.Hit(source="huggingface", id=model_id, created=created, license=license, pipeline=pipeline,
                       params=params, formats=formats or [], downloads=downloads,
                       url=f"https://huggingface.co/{model_id}")


class FakeSource:
    """Stands in for Hugging Face: canned search results and in-memory files."""
    name, title, installable = "huggingface", "Fake Hub", True

    def __init__(self, hits=(), files=None, configs=None, fail=None):
        self.hits, self.blobs, self.configs, self.fail = list(hits), dict(files or {}), dict(configs or {}), fail
        self.searches = 0

    def search(self, q="", author=None, sort="createdAt", limit=50, gguf=False, pipeline=None, timeout=10):
        self.searches += 1
        if self.fail:
            raise net.NetError(self.fail)
        out = [h for h in self.hits if (not author or h.id.startswith(author + "/"))]
        if gguf:
            out = [h for h in out if "gguf" in h.formats]
        if q:
            out = [h for h in out if q.lower() in h.id.lower()]
        return out

    def files(self, repo, timeout=15):
        return [catalog.FileInfo(path=path, size=len(data), sha256=hashlib.sha256(data).hexdigest())
                for (r, path), data in self.blobs.items() if r == repo]

    def config(self, repo, timeout=15):
        if repo not in self.configs:
            raise net.NetError(f"{repo} has no config")
        return self.configs[repo]

    def download_url(self, repo, path, revision="main"):
        return f"fake://{repo}/{path}"

    def opener(self):
        def open_stream(url, start=0, headers=None, timeout=30):
            parts = url[len("fake://"):].split("/")
            repo, path = "/".join(parts[:2]), "/".join(parts[2:])
            data = self.blobs[(repo, path)]
            return _Response(data[start:]), start > 0
        return open_stream


class _Response(io.BytesIO):
    status = 206

    def close(self):
        super().close()


QWEN_CONFIG = {"architectures": ["Qwen3_5ForConditionalGeneration"], "model_type": "qwen3_5",
               "text_config": {"num_hidden_layers": 64, "hidden_size": 5120}}
