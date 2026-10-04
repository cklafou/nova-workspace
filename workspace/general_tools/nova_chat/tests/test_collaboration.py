# Last updated: 2026-10-04 14:34:47
# @nova: Verify collaboration isolation, authentication, durable replay and concurrent delivery without starting Nova.
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from general_tools.nova_chat.collaboration import CollaborationStore, create_router, default_directory


class DirectoryTests(unittest.TestCase):
    def test_host_user_directory_is_stable_across_appdata_virtualization(self):
        home = Path("C:/Users/fixture")
        expected = home / "ProjectNovaData" / "Collaboration"
        with patch("general_tools.nova_chat.collaboration.Path.home", return_value=home):
            for appdata in [home / "AppData/Local",
                            home / "AppData/Local/Packages/Claude/LocalCache/Local"]:
                with patch.dict(os.environ, {"LOCALAPPDATA": str(appdata),
                                              "NOVA_COLLABORATION_DIR": ""}):
                    self.assertEqual(default_directory(), expected)

    def test_explicit_shared_directory_overrides_home_without_creating_or_migrating(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "explicit-shared-room"
            with patch.dict(os.environ, {"NOVA_COLLABORATION_DIR": str(target)}), \
                 patch("general_tools.nova_chat.collaboration.Path.home", side_effect=AssertionError("Override must not depend on app home")):
                self.assertEqual(default_directory(), target)
                self.assertFalse(target.exists())

    def test_unset_override_uses_user_home_without_appdata(self):
        home = Path("C:/Users/fixture")
        with patch.dict(os.environ, {}, clear=True), \
             patch("general_tools.nova_chat.collaboration.Path.home", return_value=home):
            self.assertEqual(default_directory(), home / "ProjectNovaData" / "Collaboration")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CollaborationStore(Path(self.temp.name))

    def test_restart_replay_dedupe_and_conflicting_retry(self):
        first = self.store.publish("codex", "Proposal", "retry-id")
        restarted = CollaborationStore(Path(self.temp.name))
        self.assertEqual(restarted.tokens, self.store.tokens)
        self.assertEqual(restarted.publish("codex", "Proposal", "retry-id"), first)
        with self.assertRaises(ValueError):
            restarted.publish("codex", "Changed proposal", "retry-id")
        self.assertEqual(restarted.events(0)["events"], [first])
        self.assertEqual(restarted.state()["participants"][1]["state"], "offline")

    def test_concurrent_publish_keeps_unique_order_and_pagination(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            events = list(pool.map(lambda i: self.store.publish("codex", str(i), str(i)), range(120)))
        self.assertEqual(len({e["seq"] for e in events}), 120)
        first = self.store.events(0)
        self.assertTrue(first["has_more"])
        second = self.store.events(first["cursor"])
        self.assertEqual(len(first["events"] + second["events"]), 120)
        self.assertEqual(second["cursor"], 120)
        self.assertFalse(second["has_more"])

    def test_presence_expires_and_read_cursor_never_decreases(self):
        self.store.touch("claude", "waiting", 12)
        self.store.touch("claude", "active", 3)
        self.assertEqual(self.store.state()["participants"][2]["last_read"], 12)
        with patch("general_tools.nova_chat.collaboration.time.time", return_value=time.time()+100):
            self.assertEqual(self.store.state()["participants"][2]["state"], "offline")

    def test_room_has_no_nova_ingestion_dependency(self):
        import ast
        source = Path(__file__).parents[1] / "collaboration.py"
        imports = []
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
        self.assertFalse(any("nova_" in name or "transcript" in name for name in imports))
        self.store.publish("cole", "@Nova must remain private", "privacy")
        self.assertFalse(self.store.state()["nova_access"])
        self.assertEqual({p.name for p in Path(self.temp.name).iterdir()},
                         {"credentials.json", "workshop.sqlite3"})


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CollaborationStore(Path(self.temp.name))
        app = FastAPI()
        app.include_router(create_router(self.store))
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 42000))
        self.client = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765")
        self.addAsyncCleanup(self.client.aclose)

    async def test_cross_origin_forwarded_and_foreign_host_rejected(self):
        for headers in ({"origin": "https://evil.invalid"}, {"host":"evil.invalid:8765"},
                        {"sec-fetch-site":"cross-site"}, {"x-forwarded-for":"127.0.0.1"}):
            response = await self.client.get("/api/collaboration/state", headers=headers)
            self.assertEqual(response.status_code, 403)

    async def test_agent_identity_requires_credential_and_cannot_be_payload_spoofed(self):
        data = {"text":"hello", "client_message_id":"1", "participant":"claude"}
        response = await self.client.post("/api/collaboration/messages", json=data)
        self.assertEqual(response.json()["participant"], "cole")
        headers = {"x-nova-collaboration-participant":"claude"}
        response = await self.client.post("/api/collaboration/messages", json=data, headers=headers)
        self.assertEqual(response.status_code, 401)
        headers["authorization"] = "Bearer " + self.store.tokens["claude"]
        response = await self.client.post("/api/collaboration/messages", json=data, headers=headers)
        self.assertEqual(response.json()["participant"], "claude")
        self.assertEqual(response.json()["label"], "Claude Cowork")

    async def test_long_poll_receives_publish_and_timeout_is_empty(self):
        async def publish_later():
            await asyncio.sleep(.05)
            await self.client.post("/api/collaboration/messages", json={"text":"@Nova private", "client_message_id":"x"})
        sending = asyncio.create_task(publish_later())
        response = await self.client.get("/api/collaboration/events?after=0&wait=1")
        await sending
        self.assertEqual(response.json()["events"][0]["text"], "@Nova private")
        response = await self.client.get("/api/collaboration/events?after=1&wait=0.05")
        self.assertEqual(response.json()["events"], [])

    async def test_bounds_and_duplicate_payload_errors(self):
        response = await self.client.get("/api/collaboration/events?after=-1")
        self.assertEqual(response.status_code, 422)
        response = await self.client.post("/api/collaboration/messages", json={"text":"x"*16001,"client_message_id":"x"})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post("/api/collaboration/messages", data="text=x")
        self.assertIn(response.status_code, (415, 422))


if __name__ == "__main__":
    unittest.main()
