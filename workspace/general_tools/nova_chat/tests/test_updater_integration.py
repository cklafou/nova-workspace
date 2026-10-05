# Last updated: 2026-10-05 21:27:11
# @nova: Verify updater routing and cancellable controller metadata checks using temporary models and fake catalogs only.
import ast
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "general_tools/nova_chat/server.py"
sys.path.insert(0, str(ROOT / "general_tools"))
from nova_updater import api, check, gguf, paths


def extract(names, ns):
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for n in nodes: n.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SERVER), "exec"), ns)
    return ns


def mount_server_updater(app, chat_only, restart):
    # Execute the real server registration statement, preserving its callback expression.
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                        and a.func.id == "create_updater_router" for a in n.value.args))
    ns = {"app": app, "CHAT_ONLY": chat_only, "create_updater_router": api.create_router,
          "_rt_llama": types.SimpleNamespace(restart=restart),
          "_nova_lifecycle": types.SimpleNamespace(pending=False)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SERVER), "exec"), ns)
    ns.update({"Request": Request, "JSONResponse": JSONResponse,
               "_CHAT_ONLY_MESSAGE": "Nova disabled in chat-only mode",
               "_LOCAL_HOSTS": {"127.0.0.1", "::1"}})
    extract({"_chat_only_blocks", "_chat_only_rejection", "_auth_gate"}, ns)
    app.middleware("http")(ns["_auth_gate"])


class UpdaterRouteIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.env = patch.dict(os.environ, {
            "NOVA_WORKSPACE": str(self.root), "NOVA_MODELS_DIR": str(self.root / "models"),
            "NOVA_BODY": str(self.root / "nova_body"), "NOVA_LAUNCHER": str(self.root / "launcher.cmd"),
            "NOVA_UPDATER_STATE": str(self.root / "updater-state"),
            "NOVA_UPDATER_CREDENTIALS": str(self.root / "credentials.json"),
            "NOVA_UPDATER_WORK": str(self.root / "Temp/updater"),
            "NOVA_TRASH_DIR": str(self.root / "Trash")})
        self.env.start(); self.addCleanup(self.env.stop)
        (self.root / "launcher.cmd").write_text('set "NOVA_MODEL=models/Qwen3.6-27B-Q6_K.gguf"', encoding="utf-8")
        (self.root / "models").mkdir()
        self.restart = Mock(return_value={"ok": True})
        self.client = self.make_client(True)

    def make_client(self, chat_only):
        app = FastAPI(); mount_server_updater(app, chat_only, self.restart)
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 44000))
        client = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765")
        self.addAsyncCleanup(client.aclose)
        return client

    async def test_status_in_chat_only_reads_metadata_without_model_inventory(self):
        with patch.object(api.inventory, "scan", side_effect=AssertionError("status scanned models")):
            response = await self.client.get("/api/updater/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["current"]["label"], "Qwen3.6-27B")
        self.assertIn("settings", data); self.assertIn("credentials", data)
        self.restart.assert_not_called()

    async def test_real_inventory_route_is_limited_to_disposable_fixture(self):
        self.assertEqual(paths.models_root(), self.root / "models")
        fixture = paths.models_root() / "Qwen3.6-27B-Q6_K.gguf"
        gguf.write_minimal(fixture, {"general.architecture": "qwen35", "general.name": "Qwen3.6 27B",
                                    "general.basename": "Qwen3.6", "general.size_label": "27B"})
        response = await self.client.get("/api/updater/inventory")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Qwen3.6-27B-Q6_K.gguf", response.text)
        self.restart.assert_not_called()

    async def test_foreign_browser_requests_and_non_json_posts_rejected_by_mounted_router(self):
        for headers in [{"origin": "http://evil.invalid"}, {"host": "evil.invalid:8765"},
                        {"x-forwarded-for": "127.0.0.1"}, {"sec-fetch-site": "same-site"}]:
            response = await self.client.get("/api/updater/status", headers=headers)
            self.assertEqual(response.status_code, 403)
        response = await self.client.post("/api/updater/check", content="force=true",
                                          headers={"content-type": "application/x-www-form-urlencoded"})
        self.assertEqual(response.status_code, 415)

    async def test_install_receives_restart_callback_only_in_normal_mode(self):
        job = types.SimpleNamespace(to_dict=lambda: {"id": "fixture", "state": "queued"})
        for chat_only in [True, False]:
            client = self.client if chat_only else self.make_client(False)
            with patch.object(api.plan, "load", return_value={"id": "fixture"}), \
                 patch.object(api.install, "start", return_value=job) as start:
                response = await client.post("/api/updater/install", json={"plan_id": "fixture", "confirm": True})
            self.assertEqual(response.status_code, 200)
            self.assertIs(start.call_args.kwargs["restart"], None if chat_only else self.restart)
        self.restart.assert_not_called()


class UpdaterStartupIntegration(unittest.IsolatedAsyncioTestCase):
    def helpers(self, check_function):
        return extract({"_updater_startup_check", "_start_updater_check", "_stop_updater_check"},
                       {"asyncio": asyncio, "_updater_check_task": None,
                        "updater_check": types.SimpleNamespace(run_check=check_function)})

    async def test_startup_schedules_one_cancellable_check_per_lifecycle(self):
        run = Mock(); ns = self.helpers(run)
        ns["_start_updater_check"](); first = ns["_updater_check_task"]
        ns["_start_updater_check"]()
        self.assertIs(ns["_updater_check_task"], first)
        await ns["_stop_updater_check"]()
        self.assertIsNone(ns["_updater_check_task"])
        self.assertTrue(first.cancelled())
        run.assert_not_called()

    async def test_slow_catalog_never_blocks_loop_and_shutdown_cancels_waiter(self):
        started = threading.Event(); release = threading.Event()
        def slow_check():
            started.set(); release.wait(2)
        ns = self.helpers(slow_check)
        task = asyncio.create_task(ns["_updater_startup_check"](0))
        ns["_updater_check_task"] = task
        try:
            async def wait_started():
                while not started.is_set(): await asyncio.sleep(0.005)
            await asyncio.wait_for(wait_started(), 0.5)
            # The catalog is still blocked; cancellation must not wait on its HTTP worker.
            await asyncio.wait_for(ns["_stop_updater_check"](), 0.2)
            self.assertTrue(task.cancelled())
            self.assertFalse(release.is_set())
        finally:
            release.set()

    async def test_failed_check_does_not_break_startup_and_completion_does_not_repeat(self):
        ns = self.helpers(Mock(side_effect=ValueError("fixture offline")))
        task = asyncio.create_task(ns["_updater_startup_check"](0))
        ns["_updater_check_task"] = task
        await task
        ns["_start_updater_check"]()
        self.assertIs(ns["_updater_check_task"], task)
        await ns["_stop_updater_check"]()

    async def test_startup_check_runs_in_both_modes_before_body_jobs(self):
        for chat_only in [True, False]:
            order = []
            def schedule(coro): coro.close()
            async def noop(): pass
            rt = Mock(); rt.start_indexer.side_effect = lambda: order.append("body")
            ns = {"CHAT_ONLY": chat_only, "_start_updater_check": lambda: order.append("updater"),
                  "asyncio": types.SimpleNamespace(ensure_future=schedule, to_thread=AsyncMock()),
                  "_window_close_watchdog": noop, "autonomy_daemon": noop,
                  "_rt": rt, "CLIENT_MAP": {"Nova": object()}}
            cortex = types.ModuleType("nova_cortex")
            cortex.executive = types.SimpleNamespace(autonomy_enabled=lambda: False)
            with patch.dict(sys.modules, {"nova_cortex": cortex}):
                await extract({"startup_event"}, ns)["startup_event"]()
            self.assertEqual(order, ["updater"] if chat_only else ["updater", "body"])
            if chat_only: self.assertEqual(rt.mock_calls, [])
            else: rt.model_client.register.assert_called_once_with(ns["CLIENT_MAP"])


if __name__ == "__main__": unittest.main()
