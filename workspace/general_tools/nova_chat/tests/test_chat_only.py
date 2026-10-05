# @nova: Verify model-off controller launch and prevent chat-only messages from reaching Nova's body.
# Last updated: 2026-10-05 21:49:04
import ast
import asyncio
import json
import re
from pathlib import Path
import threading
import types
import unittest
from unittest.mock import Mock, AsyncMock

from fastapi.responses import JSONResponse
from fastapi import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "general_tools/nova_chat/server.py"
LAUNCHER = ROOT / "nova_start.py"


def extract(path, names, ns):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


class ChatOnlyTests(unittest.TestCase):
    def test_no_body_background_work_or_model_shutdown(self):
        scheduled = []
        rt = Mock()
        fake_async = types.SimpleNamespace(ensure_future=scheduled.append)
        ns = {"CHAT_ONLY": True, "asyncio": fake_async, "_rt": rt,
              "_window_close_watchdog": lambda: "window-lifecycle-only",
              "_start_updater_check": Mock(), "_stop_updater_check": AsyncMock(),
              "_voice_controller": types.SimpleNamespace(close=AsyncMock())}
        extract(SERVER, {"startup_event", "shutdown_event"}, ns)
        asyncio.run(ns["startup_event"]())
        asyncio.run(ns["shutdown_event"]())
        self.assertEqual(scheduled, ["window-lifecycle-only"])
        self.assertEqual(rt.mock_calls, [])
        ns["_start_updater_check"].assert_called_once()
        ns["_stop_updater_check"].assert_awaited_once()
        ns["_voice_controller"].close.assert_awaited_once()

    def test_model_off_status_does_not_query_body_or_provider(self):
        client = types.SimpleNamespace(is_available=AsyncMock())
        ns = {"CHAT_ONLY": True, "nova_client": client, "_CHAT_ONLY_MESSAGE": "disabled"}
        extract(SERVER, {"get_status", "runtime_state"}, ns)
        self.assertFalse(asyncio.run(ns["get_status"]())["Nova"])
        state = asyncio.run(ns["runtime_state"]())
        self.assertTrue(state["chat_only"])
        self.assertFalse(state["autonomy_enabled"])
        self.assertEqual(state["operations"], [])
        client.is_available.assert_not_called()

    def test_http_ingress_and_activation_blocked_but_collaboration_and_human_tools_work(self):
        ns = extract(SERVER, {"_chat_only_blocks"}, {"CHAT_ONLY": True})
        gate = ns["_chat_only_blocks"]
        for path in ["/api/llama/start", "/api/restart/server", "/api/wake", "/api/runtime/resume",
                     "/api/inject_message", "/nova-message", "/api/lora/equip", "/api/computer/handoff",
                     "/api/runtime/recover-memory", "/api/reinject_context", "/sessions/new"]:
            self.assertTrue(gate(path, "POST"), path)
        self.assertTrue(gate("/api/lora/available", "GET"))
        for path, method in [("/api/collaboration/messages", "POST"), ("/api/collaboration/events", "GET"),
                             ("/api/terminal/run", "POST"), ("/api/restart/full", "POST"),
                             ("/api/files/tree", "GET")]:
            self.assertFalse(gate(path, method), path)
        ns["CHAT_ONLY"] = False
        self.assertFalse(gate("/api/wake", "POST"))

    def test_websocket_messages_never_touch_session_runtime_or_indexer(self):
        class Socket:
            def __init__(self):
                self.out = []
                self.inputs = iter([{"type": "message", "content": "Private collaboration", "request_id": "off-request"},
                                    {"type": "user_typing", "typing": True},
                                    {"type": "autonomous_toggle", "enabled": True}])
            async def accept(self): pass
            async def send_text(self, value): self.out.append(json.loads(value))
            async def receive_text(self):
                try: return json.dumps(next(self.inputs))
                except StopIteration: raise WebSocketDisconnect()
        ws = Socket()
        forbidden = Mock(side_effect=AssertionError("Nova body was touched"))
        ns = {"CHAT_ONLY": True, "WebSocket": object, "WebSocketDisconnect": WebSocketDisconnect,
              "json": json, "connected_clients": [], "is_processing": False,
              "autonomous_mode": False, "_mute_states": {}, "_CHAT_ONLY_MESSAGE": "disabled",
              "session_mgr": None, "get_status": AsyncMock(return_value={"Nova": False}),
              "re": re, "broadcast": AsyncMock(), "_request_work": {}, "_cole_message_queue": [],
              "_mirror_to_runtime": forbidden, "memory_indexer": forbidden, "_rt": forbidden}
        extract(SERVER.with_name("response_events.py"), {"normalize_request_id"}, ns)
        extract(ROOT / "nova_body/nova_runtime/model_client.py", {"normalize_register"}, ns)
        extract(SERVER, {"websocket_endpoint", "_end_queued_request", "_release_request_work"}, ns)
        asyncio.run(ns["websocket_endpoint"](ws))
        self.assertEqual(len([m for m in ws.out if m["type"] == "error"]), 2)
        self.assertTrue(all(m.get("enabled") is False for m in ws.out if m["type"] == "autonomous_state"))
        forbidden.assert_not_called()
        ns["broadcast"].assert_awaited_once_with({"type": "request_end", "request_id": "off-request",
                                                "reply_to": None, "register": "text", "delivery": "unavailable"})
        self.assertEqual(ns["connected_clients"], [])

    def test_launcher_never_starts_models_watcher_guardian_in_chat_only(self):
        signal = threading.Event(); signal.set()
        events = []
        ns = {"CHAT_ONLY": True, "HUB": None, "_SHUTDOWN": signal, "WS": ROOT,
              "_check_controller_mode": lambda: None, "_configure_nova_mode": lambda *args: None, "CHAT_PORT": 8765, "_app_backend": "qt",
              "time": types.SimpleNamespace(time=lambda: 0), "banner": Mock(), "log": Mock(),
              "_watch_for_shutdown": Mock(), "_wait_for_process": Mock(),
              "wait_for_nova": lambda: True, "_shutdown_nova": Mock()}
        for name in ["llama", "witness", "watcher", "guardian"]:
            ns["start_"+name] = Mock(side_effect=AssertionError("Unexpected start: "+name))
            ns["stop_"+name] = Mock()
        for name in ["nova", "console", "app"]:
            proc = Mock(pid=1); proc.poll.return_value = 0
            ns["open_app_window" if name == "app" else "start_"+name] = Mock(return_value=proc)
        extract(LAUNCHER, {"main"}, ns)["main"]()
        for name in ["llama", "witness", "watcher", "guardian"]:
            ns["start_"+name].assert_not_called()
            ns["stop_"+name].assert_called_once_with(None)

    def test_restart_preserves_chat_only_argument(self):
        spawn = Mock(return_value=types.SimpleNamespace(pid=123))
        ns = {"CHAT_ONLY": True, "CHAT_PORT": 8765, "port_open": lambda p: False,
              "sys": types.SimpleNamespace(executable="python"), "Path": Path,
              "__file__": str(LAUNCHER), "subprocess": types.SimpleNamespace(Popen=spawn),
              "WS": ROOT, "_NO_WINDOW": 0, "log": Mock()}
        extract(LAUNCHER, {"_relaunch_after_shutdown"}, ns)["_relaunch_after_shutdown"]()
        self.assertEqual(spawn.call_args.args[0][-1], "--chat-only")

    def test_existing_normal_controller_is_rejected_before_launch(self):
        response = Mock()
        response.__enter__ = Mock(return_value=types.SimpleNamespace(read=lambda: b'{"chat_only": false}'))
        response.__exit__ = Mock(return_value=False)
        ns = {"CHAT_ONLY": True, "CHAT_PORT": 8765, "port_open": lambda p: True,
              "urllib": types.SimpleNamespace(request=types.SimpleNamespace(urlopen=lambda *a, **k: response)),
              "json": json}
        check = extract(LAUNCHER, {"_check_controller_mode"}, ns)["_check_controller_mode"]
        with self.assertRaisesRegex(RuntimeError, "different mode"):
            check()


if __name__ == "__main__":
    unittest.main()
