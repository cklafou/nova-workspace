# Last updated: 2026-10-04 13:56:40
# @nova: Test launcher mode switching, window preservation and chat-only recovery using fake processes only.
import ast
import io
import json
import urllib.request
import urllib.error
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from general_tools.nova_console.hub import LogHub
from general_tools.nova_console.lifecycle import NovaModeState, NovaServiceSwitch
ROOT = Path(__file__).resolve().parents[3]


def functions(names, ns):
    tree = ast.parse((ROOT / "nova_start.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in nodes:
        node.returns = None
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "launcher-fixture", "exec"), ns)
    return ns


class FakeProcess:
    def __init__(self, name):
        self.name, self.pid, self.dead = name, 123, False
    def poll(self): return 0 if self.dead else None
    def wait(self, timeout=None):
        if not self.dead: raise TimeoutError("still running")
        return 0


class ModeQueue(unittest.TestCase):
    def test_grace_retry_conflict_and_single_execution(self):
        now = [0]
        apply = Mock(return_value={"chat_only": False})
        state = NovaModeState(True, apply, clock=lambda: now[0])
        self.assertEqual(state.request(False)[1], 202)
        now[0] = 0.9
        self.assertEqual(state.request(False)[1], 202)
        self.assertEqual(state.request(True)[1], 409)
        self.assertFalse(state.process())
        now[0] = 1
        self.assertTrue(state.process())
        self.assertFalse(state.process())
        apply.assert_called_once_with(False)
        self.assertEqual(state.snapshot()["state"], "on")
        self.assertEqual(state.request(False)[1], 200)

    def test_full_restart_and_mode_switch_cannot_race(self):
        hub = LogHub(ROOT); hub.configure_nova(True, Mock())
        self.assertEqual(hub.request_nova("start")[1], 202)
        self.assertEqual(hub.request_lifecycle("restart")[1], 409)
        self.assertEqual(hub.request_lifecycle("shutdown")[1], 409)
        other = LogHub(ROOT); other.configure_nova(True, Mock())
        self.assertEqual(other.request_lifecycle("shutdown")[1], 202)
        self.assertEqual(other.request_nova("start")[1], 409)

    def test_error_retains_actual_mode_and_allows_retry(self):
        self.assertEqual(LogHub(ROOT).request_nova("start")[1], 503)
        now = [0]
        state = NovaModeState(True, lambda _: {"chat_only": True, "error": "Failed; chat restored"}, clock=lambda: now[0])
        state.request(False); now[0] = 2; state.process()
        self.assertEqual(state.snapshot()["state"], "error")
        self.assertTrue(state.snapshot()["chat_only"])
        self.assertFalse(state.snapshot()["pending"])
        self.assertEqual(state.request(False)[1], 202)


class ServiceSwitch(unittest.TestCase):
    def fixture(self, enabled=False):
        self.events = []
        self.window, self.console = FakeProcess("window"), FakeProcess("console")
        services = {name: FakeProcess(name) if enabled or name == "nova" else None for name in NovaServiceSwitch.ORDER}
        def start(name):
            self.events.append("start:" + name); return FakeProcess(name)
        def stop(name, proc):
            self.events.append("stop:" + name)
            if proc: proc.dead = True
        switch = NovaServiceSwitch(services,
            start={n: lambda n=n: start(n) for n in NovaServiceSwitch.ORDER},
            stop={n: lambda p, n=n: stop(n,p) for n in NovaServiceSwitch.ORDER},
            verify_down=lambda: self.events.append("ports:closed"),
            set_mode=lambda value: self.events.append("mode:" + str(value)),
            wait_model=lambda: True, wait_worker=lambda mode: True, wait_witness=lambda: True, publish=lambda: None)
        switch.chat_only = not enabled
        return switch, services

    def test_start_stop_keeps_window_and_console_and_stops_guardian_first(self):
        switch, services = self.fixture()
        self.assertEqual(switch(False), {"chat_only": False})
        self.assertEqual(self.events[:6], ["stop:guardian", "stop:watcher", "stop:nova", "stop:llama", "stop:witness", "ports:closed"])
        self.assertLess(self.events.index("ports:closed"), self.events.index("mode:False"))
        self.assertLess(self.events.index("start:llama"), self.events.index("start:nova"))
        self.assertLess(self.events.index("start:nova"), self.events.index("start:guardian"))
        previous = services["nova"]; self.events.clear()
        self.assertEqual(switch(True), {"chat_only": True})
        self.assertTrue(previous.dead); self.assertIsNot(previous, services["nova"])
        self.assertEqual([e for e in self.events if e.startswith("start:")], ["start:nova"])
        self.assertFalse(self.window.dead); self.assertFalse(self.console.dead)

    def test_failed_model_load_recovers_chat_only(self):
        switch, services = self.fixture(); switch.wait_model = lambda: False
        result = switch(False)
        self.assertTrue(result["chat_only"]); self.assertIn("model did not become ready",result["error"])
        self.assertIsNone(services["llama"]); self.assertIsNotNone(services["nova"])
        self.assertNotIn("start:guardian", self.events); self.assertFalse(self.window.dead)

    def test_failed_normal_worker_recovers_chat_only(self):
        switch, services = self.fixture(); switch.wait_worker = lambda mode: mode
        result = switch(False)
        self.assertTrue(result["chat_only"]); self.assertIn("restored",result["error"])
        self.assertEqual(self.events.count("start:nova"), 2)
        self.assertNotIn("start:guardian",self.events); self.assertFalse(self.window.dead)

    def test_ports_must_close_before_any_new_generation(self):
        switch, services = self.fixture(True)
        def stuck(): raise RuntimeError("8080 still open")
        switch.verify_down = stuck
        self.assertIn("8080", switch(True)["error"])
        self.assertFalse(any(e.startswith("start:") for e in self.events))

    def test_unstoppable_guardian_prevents_body_teardown(self):
        switch, services = self.fixture(True)
        switch.stop["guardian"] = lambda proc: None
        self.assertIn("guardian did not stop",switch(True)["error"])
        self.assertNotIn("stop:nova",self.events); self.assertFalse(services["nova"].dead)

    def test_system_exit_from_model_start_is_recoverable(self):
        switch, services = self.fixture()
        def failed(): raise SystemExit(2)
        switch.start["llama"] = failed
        result = switch(False)
        self.assertTrue(result["chat_only"]); self.assertIsNotNone(services["nova"])
        self.assertFalse(self.window.dead)


class Wiring(unittest.TestCase):
    def test_model_start_uses_authoritative_launcher_not_stale_model_constants(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / "start_llama_qwen36.cmd").write_text("@echo off")
            ns = functions({"start_llama"},{"llama_healthy":lambda:False,"port_open":lambda p:False,
                "LLAMA_PORT":8080,"WS":folder,"LLAMA_LOGS":folder,"_STAMP":"fixture","log":Mock(),
                "sys":types.SimpleNamespace(platform="win32"),"subprocess":subprocess,"_hidden_console":lambda:{}})
            with patch.object(subprocess,"Popen",return_value=FakeProcess("cmd")) as spawn:
                ns["start_llama"]()
            self.assertEqual(spawn.call_args.args[0],["cmd","/c",str(folder / "start_llama_qwen36.cmd")])
            self.assertNotIn("MODEL",ns)

    def test_wait_follows_replacement_worker(self):
        old,new = FakeProcess("old"),FakeProcess("new"); current=[old]; calls=[]
        def step():
            calls.append(current[0].name); old.dead=True; current[0]=new
            if len(calls)==2: new.dead=True
        ns=functions({"_wait_for_process"},{"_SHUTDOWN":types.SimpleNamespace(wait=lambda _:False),"_poll_nova_mode":step})
        ns["_wait_for_process"](old,current=lambda:current[0])
        self.assertEqual(calls,["old","new"])

    def test_changed_mode_updates_environment_for_later_restarts(self):
        env={};ns=functions({"_set_controller_mode"},{"os":types.SimpleNamespace(environ=env),"CHAT_ONLY":True})
        ns["_set_controller_mode"](False);self.assertFalse(ns["CHAT_ONLY"]);self.assertEqual(env["NOVA_CHAT_ONLY"],"0")
        ns["_set_controller_mode"](True);self.assertEqual(env["NOVA_CHAT_ONLY"],"1")


class ShutdownDuringLoad(unittest.TestCase):
    def test_model_and_witness_waits_cancel_before_health_or_sleep(self):
        for name in ("wait_for_llama", "wait_for_witness"):
            forbidden = Mock(side_effect=AssertionError("readiness probe after cancellation"))
            ns=functions({name},{"time":types.SimpleNamespace(time=lambda:0,sleep=forbidden),
                "_SHUTDOWN":types.SimpleNamespace(is_set=lambda:False),"banner":Mock(),"log":Mock(),
                "llama_healthy":forbidden,"witness_healthy":forbidden})
            self.assertFalse(ns[name](cancelled=lambda:True))
            forbidden.assert_not_called()

    def test_worker_wait_cancels_before_any_http_probe(self):
        ns=functions({"_wait_controller_mode"},{"time":types.SimpleNamespace(monotonic=lambda:0),
            "_SHUTDOWN":types.SimpleNamespace(is_set=lambda:False)})
        self.assertFalse(ns["_wait_controller_mode"](False,cancelled=lambda:True))


class WorkerCleanup(unittest.TestCase):
    def fixture(self, result, listening=True):
        shutdown = Mock()
        response = io.BytesIO(json.dumps(result).encode())
        opener = Mock(return_value=response)
        ns = functions({"_stop_mode_worker"}, {"CHAT_PORT":8765, "port_open":lambda _:listening,
            "urllib":types.SimpleNamespace(request=types.SimpleNamespace(Request=urllib.request.Request,urlopen=opener)),
            "json":json,"_shutdown_nova":shutdown})
        return ns["_stop_mode_worker"], opener, shutdown

    def test_flush_acknowledged_before_worker_termination(self):
        stop, opener, shutdown = self.fixture({"ok":True,"stopped":True})
        proc=FakeProcess("nova")
        stop(proc)
        request=opener.call_args.args[0]
        self.assertEqual(request.full_url,"http://127.0.0.1:8765/api/nova/quiesce")
        self.assertEqual(request.method,"POST"); self.assertEqual(request.data,b"{}")
        self.assertEqual(opener.call_args.kwargs["timeout"],20)
        shutdown.assert_called_once_with(proc)

    def test_undrained_or_failed_cleanup_preserves_worker(self):
        for result in ({"ok":True,"stopped":False},{"ok":False,"stopped":True},{}):
            stop, opener, shutdown=self.fixture(result)
            with self.assertRaisesRegex(RuntimeError,"worker was preserved"):
                stop(FakeProcess("nova"))
            shutdown.assert_not_called()
        stop,opener,shutdown=self.fixture({})
        opener.side_effect=TimeoutError("cleanup timed out")
        with self.assertRaisesRegex(RuntimeError,"timed out"):stop(FakeProcess("nova"))
        shutdown.assert_not_called()

    def test_does_not_quiesce_an_unowned_controller(self):
        for proc in (None,FakeProcess("old")):
            if proc:proc.dead=True
            stop,opener,shutdown=self.fixture({"ok":True,"stopped":True})
            with self.assertRaisesRegex(RuntimeError,"does not own"):stop(proc)
            opener.assert_not_called();shutdown.assert_not_called()

    def test_worker_without_listener_can_be_terminated_for_recovery(self):
        stop,opener,shutdown=self.fixture({},listening=False)
        proc=FakeProcess("failed boot")
        stop(proc)
        opener.assert_not_called();shutdown.assert_called_once_with(proc)


class HubRoutes(unittest.TestCase):
    def test_local_proxy_route_acknowledges_and_cross_site_requests_cannot_start(self):
        hub=LogHub(ROOT);hub.configure_nova(True,Mock());hub.serve(0)
        try:
            url=f"http://127.0.0.1:{hub._httpd.server_port}"
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url+"/api/nova/status",timeout=2) as response:
                self.assertEqual(json.load(response)["state"],"off")
            for headers in ({"Origin":"https://example.invalid"},{"X-Forwarded-Host":"example.invalid"},
                            {"Host":"example.invalid"},{"Content-Type":"text/plain"}):
                request=urllib.request.Request(url+"/api/nova/start",data=b"{}",method="POST",
                    headers={"Content-Type":"application/json",**headers})
                with self.assertRaises(urllib.error.HTTPError) as error:opener.open(request,timeout=2)
                self.assertEqual(error.exception.code,403)
                self.assertFalse(hub.nova_status()["pending"])
            request=urllib.request.Request(url+"/api/nova/start",data=b"{}",method="POST",
                headers={"Content-Type":"application/json"})
            with opener.open(request,timeout=2) as response:
                self.assertEqual(response.status,202)
                result=json.load(response)
                self.assertEqual(result["state"],"starting");self.assertTrue(result["pending"])
            self.assertEqual(hub.request_nova("unknown")[1],400)
        finally:
            hub.shutdown()
