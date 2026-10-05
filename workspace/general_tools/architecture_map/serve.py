# Last updated: 2026-10-06 03:19:20
"""Serve and automatically regenerate the read-only Nova architecture atlas.

Only this atlas is started. No Nova modules are imported, no model is started, and no
memory/state files are written. The default bind address is loopback only.
"""
from __future__ import annotations

# Body-owned paths also work when this tool is launched directly.
import sys as _nova_path_sys
from pathlib import Path as _NovaPath
_nova_path_sys.path.insert(0, str(_NovaPath(__file__).resolve().parents[2] / 'nova_body'))
from nova_paths import body_path

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from build import DEFAULT_WORKSPACE, HERE, atomic_write, collect, digest, source_files, supporting_files, write_outputs
from atlas_history import head_revision, history_diff

APP = "nova-architecture-atlas"


def watched_signature(workspace, assets=HERE, catalog_path=None):
    """Content hashes catch edits even if a filesystem preserves size/mtime."""
    workspace, assets = Path(workspace), Path(assets)
    paths = set(source_files(workspace))
    paths.update(supporting_files(workspace))
    paths.update(p for p in assets.iterdir() if p.suffix in {".py", ".js", ".css", ".html", ".json"})
    paths.update(workspace / p for p in ["nova_body/nova_config.json", "start_llama_qwen36.cmd", "NovaStart.cmd", "StopNova.cmd"])
    paths.update((body_path('KoELS', workspace=workspace)).rglob("manifest.json"))

    if catalog_path:
        paths.add(Path(catalog_path))
    h = hashlib.sha256()
    h.update(head_revision(workspace).encode())
    timeline_path = Path(catalog_path or HERE / "catalog.json").parent / "timeline.json"
    if timeline_path.exists():
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        paths.add(timeline_path)
        for item in timeline.get("milestones", []):
            for ref in item.get("refs", []):
                candidate = (workspace / ref["file"]).resolve()
                if candidate.is_relative_to(workspace.resolve()):
                    paths.add(candidate)
    for p in sorted(paths):
        h.update(str(p).encode())
        try:
            h.update(p.read_bytes())
        except FileNotFoundError:
            h.update(b"absent")
    # Changes to mapped state/data affect metadata, never copy their contents into the map.
    for rel in ["nova_body/SELF", "nova_body/SELF/core", "nova_body/memory", "nova_body/Tasking", "nova_body/logs", "nova_body/nova_memory_db", "nova_body/KoELS", "nova_body/memory/tunables.json"]:
        p = workspace / rel
        h.update(rel.encode())
        entries = [p] + (sorted(p.iterdir()) if p.is_dir() else [])
        for entry in entries:
            try:
                st = entry.stat()
                h.update(f"{entry.name}:{st.st_size}:{st.st_mtime_ns}".encode())
            except FileNotFoundError:
                h.update(b"absent")
    return h.hexdigest()


class Atlas:
    def __init__(self, workspace=DEFAULT_WORKSPACE, output=None, catalog=None, interval=2.0):
        self.workspace = Path(workspace).resolve()
        self.output = Path(output or self.workspace / "Orient" / "Architecture").resolve()
        self.catalog = Path(catalog or HERE / "catalog.json").resolve()
        self.interval = interval
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.error = None
        self.last_checked = None
        self.last_change = None
        self.data = None
        self.signature = None
        self.token = secrets.token_urlsafe(32)
        self.asset_revision = ""
        self.service_cache = (0, [])
        self.rebuild()

    def rebuild(self):
        before = watched_signature(self.workspace, catalog_path=self.catalog)
        new_data = collect(self.workspace, self.catalog)
        # Include non-Python definitions and resource metadata changes in the revision.
        new_data["source_revision"] = before[:16]
        new_data["revision"] = digest(new_data["revision"] + before)[:16]
        asset_revision = digest("".join((HERE / name).read_text(encoding="utf-8") for name in ["viewer.html", "viewer.css", "viewer.js", "experience.js"]))[:16]
        after = watched_signature(self.workspace, catalog_path=self.catalog)
        if before != after:
            raise RuntimeError("Source changed during extraction; retrying after the next stable scan")
        with self.lock:
            write_outputs(new_data, self.output)
            self.data, self.signature, self.error = new_data, before, None
            self.asset_revision = asset_revision
            self.last_change = time.time()
            self.service_cache = (0, [])

    def check_once(self):
        self.last_checked = time.time()
        try:
            signature = watched_signature(self.workspace, catalog_path=self.catalog)
            if signature != self.signature:
                self.rebuild()
                return True
            self.error = None
        except Exception as exc:
            # Keep the last good graph and make failures visible, rather than erasing it.
            self.error = f"{type(exc).__name__}: {exc}"
        return False

    def watch(self):
        while not self.stop_event.wait(self.interval):
            self.check_once()

    def services(self):
        now = time.monotonic()
        if now - self.service_cache[0] < 20:
            return self.service_cache[1]
        with self.lock:
            resources = list(self.data["resources"])
        result = []
        for item in resources:
            host = item.get("host", "127.0.0.1")
            port = item.get("port")
            if not port or host not in {"localhost", "127.0.0.1", "::1"}:
                continue
            listening = False
            try:
                with socket.create_connection((host, int(port)), timeout=0.15):
                    listening = True
            except OSError:
                pass
            result.append({"id": item["id"], "host": host, "port": port, "listening": listening,
                           "evidence": "TCP connection only; service identity/inference not verified"})
        self.service_cache = now, result
        return result

    def status(self):
        return {"app": APP, "workspace": str(self.workspace), "watching": not self.stop_event.is_set(),
                "revision": self.data["revision"], "asset_revision": self.asset_revision,
                "error": self.error, "checked_at": self.last_checked, "changed_at": self.last_change,
                "services": self.services()}

    def source(self, relative, line):
        """Allow only the mapped source inventory, after resolving symlinks and traversal."""
        allowed = {n["id"] for n in self.data["nodes"] + self.data.get("definitions", [])}
        allowed.update(ref["file"] for event in self.data.get("history", {}).get("milestones", []) for ref in event.get("evidence", []))
        if relative not in allowed:
            raise PermissionError("Not a mapped source file")
        path = (self.workspace / relative).resolve()
        if not path.is_relative_to(self.workspace):
            raise PermissionError("Path leaves the workspace")
        lines = path.read_text(encoding="utf-8-sig").replace("\0", "[null byte]").splitlines()
        line = max(1, min(int(line), max(1, len(lines))))
        start, end = max(1, line - 12), min(len(lines), line + 30)
        return {"file": relative, "start": start, "lines": lines[start - 1:end]}


def handler_for(atlas):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, value, status=200, content_type="application/json; charset=utf-8"):
            payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'self'")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self):
            host = self.headers.get("Host", "").split(":")[0]
            return host in {"127.0.0.1", "localhost"}

        def do_GET(self):
            if not self.allowed():
                return self.send({"error": "Loopback Host required"}, 403)
            parsed = urlsplit(self.path)
            try:
                if parsed.path in {"/api/status", "/api/health"}:
                    return self.send(atlas.status())
                if parsed.path == "/api/map":
                    with atlas.lock:
                        return self.send(atlas.data)
                if parsed.path == "/api/source":
                    params = parse_qs(parsed.query)
                    return self.send(atlas.source(params.get("path", [""])[0], params.get("line", ["1"])[0]))
                if parsed.path == "/api/history/diff":
                    params = parse_qs(parsed.query)
                    return self.send(history_diff(atlas.workspace, atlas.data.get("history", {}), params.get("day", [""])[0], params.get("path", [""])[0]))
                static = {"/": "index.html", "/index.html": "index.html", "/level-1.svg": "level-1.svg",
                          "/level-2.svg": "level-2.svg", "/architecture.json": "architecture.json"}
                if parsed.path in static:
                    file = atlas.output / static[parsed.path]
                    kind = "image/svg+xml" if file.suffix == ".svg" else "application/json" if file.suffix == ".json" else "text/html; charset=utf-8"
                    with atlas.lock:
                        return self.send(file.read_bytes(), content_type=kind)
                return self.send({"error": "Not found"}, 404)
            except PermissionError as exc:
                return self.send({"error": str(exc)}, 403)
            except (ValueError, FileNotFoundError) as exc:
                return self.send({"error": str(exc)}, 400)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                return self.send({"error": str(exc)}, 503)

        def do_POST(self):
            if not self.allowed() or self.headers.get("X-Atlas-Token") != atlas.token:
                return self.send({"error": "Local atlas token required"}, 403)
            if self.path != "/api/shutdown":
                return self.send({"error": "Not found"}, 404)
            self.send({"ok": True})
            atlas.stop_event.set()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
    return Handler


def state_path(workspace):
    return Path(workspace) / "general_tools" / "architecture_map" / "Temp" / "server.json"


def existing(workspace):
    path = state_path(workspace)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        # Validate local state instead of trusting an arbitrary stored URL.
        port = int(state["port"])
        if not 1024 <= port <= 65535:
            return None
        url = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
            result = json.load(response)
        if result.get("app") == APP and Path(result["workspace"]).resolve() == Path(workspace).resolve():
            return state | {"url": url}
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    running = existing(args.workspace)
    if running:
        if args.stop:
            request = urllib.request.Request(running["url"] + "/api/shutdown", method="POST", headers={"X-Atlas-Token": running["token"]})
            with urllib.request.urlopen(request, timeout=3) as response:
                print(response.read().decode())
        elif args.open:
            webbrowser.open(running["url"] + "/#level=3")
        else:
            print("Atlas already running at " + running["url"])
        return
    if args.stop:
        print("Atlas is not running.")
        return
    atlas = Atlas(args.workspace)
    server = None
    for port in range(args.port, min(args.port + 20, 65536)):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(atlas))
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("No free local atlas port in requested range")
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}"
    receipt = {"app": APP, "port": server.server_port, "pid": os.getpid(), "token": atlas.token}
    atomic_write(state_path(args.workspace), json.dumps(receipt))
    thread = threading.Thread(target=atlas.watch, name="ArchitectureWatcher", daemon=True)
    thread.start()
    print(f"Nova architecture atlas: {url}/#level=3", flush=True)
    if args.open:
        webbrowser.open(url + "/#level=3")
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        atlas.stop_event.set()
        server.server_close()
        thread.join(timeout=5)
        path = state_path(args.workspace)
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
                path.unlink()
        except (OSError, ValueError):
            pass


if __name__ == "__main__":
    main()
