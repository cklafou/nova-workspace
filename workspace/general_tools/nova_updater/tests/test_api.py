# @nova: Tests the updater's Nova Chat routes: the local-only guard (Host, Origin, client), status, decisions, search filters and confirmations.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v (needs fastapi + httpx)."""
import json
import unittest

from support import FakeSource, Workspace, hit

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - Nova Chat's environment has both
    FastAPI = None

from nova_updater import catalog, check

LOCAL = {"host": "127.0.0.1:8765"}


@unittest.skipIf(FastAPI is None, "fastapi/httpx not installed")
class Routes(Workspace):
    def setUp(self):
        super().setUp()
        from nova_updater.api import create_router
        self.fake = FakeSource([hit("Qwen/Qwen3.8-27B", 27_781_427_952), hit("Qwen/Qwen3.6-27B", 27_781_427_952),
                                hit("Qwen/Qwen3-30B-A3B", 30_500_000_000)])
        original = dict(catalog.SOURCES)
        fake = self.fake

        class FakeHub:
            title, installable = "Fake Hub", True

            def __new__(cls, **_):
                return fake
        catalog.SOURCES["huggingface"] = FakeHub
        self.addCleanup(lambda: (catalog.SOURCES.clear(), catalog.SOURCES.update(original)))
        app = FastAPI()
        app.include_router(create_router(allowed_clients={"testclient"}))
        self.client = TestClient(app)

    def test_guard_refuses_foreign_host_and_origin(self):
        self.assertEqual(self.client.get("/api/updater/status", headers={"host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/updater/status",
                                         headers={**LOCAL, "origin": "http://evil.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/updater/status", headers={**LOCAL, "origin": "http://127.0.0.1:8765"}).status_code, 200)

    def test_guard_matches_the_collaboration_rules(self):
        def get(**extra):
            return self.client.get("/api/updater/status", headers={**LOCAL, **extra}).status_code
        self.assertEqual(get(origin="http://127.0.0.1:9999"), 403)      # another local port is another site
        self.assertEqual(get(origin="http://127.0.0.1:8765"), 200)
        self.assertEqual(get(**{"x-forwarded-for": "203.0.113.9"}), 403)  # a tunnel would look local
        self.assertEqual(get(forwarded="for=203.0.113.9"), 403)
        self.assertEqual(get(**{"sec-fetch-site": "same-site"}), 403)
        self.assertEqual(get(**{"sec-fetch-site": "same-origin"}), 200)
        self.assertEqual(self.client.get("/api/updater/status", headers={"host": "127.0.0.1"}).status_code, 403)

    def test_mutations_must_be_json(self):
        response = self.client.post("/api/updater/check", content=b"force=true",
                                    headers={**LOCAL, "content-type": "application/x-www-form-urlencoded"})
        self.assertEqual(response.status_code, 415)

    def test_train_preview_takes_a_spec(self):
        data = self.ws / "_admin" / "Training_stuff" / "core.jsonl"
        data.parent.mkdir(parents=True, exist_ok=True)
        row = {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hey."}]}
        data.write_text(json.dumps(row) + "\n", encoding="utf-8")
        spec = {"base_model_id": "unsloth/Qwen3.8-27B", "data_files": ["_admin/Training_stuff/core.jsonl"]}
        ok = self.client.post("/api/updater/train/preview", headers=LOCAL, json={"spec": spec})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual((ok.json()["rows"], ok.json()["base_family"]), (1, "qwen3.8"))
        self.assertEqual(self.client.post("/api/updater/train/preview", headers=LOCAL, json=spec).status_code, 400)

    def test_guard_refuses_non_loopback_clients(self):
        from fastapi import FastAPI as F
        from nova_updater.api import create_router
        app = F()
        app.include_router(create_router())  # real loopback set: TestClient's "testclient" is not in it
        self.assertEqual(TestClient(app).get("/api/updater/status", headers=LOCAL).status_code, 403)

    def test_check_decision_flow(self):
        result = self.client.post("/api/updater/check", json={"force": True}, headers=LOCAL).json()
        self.assertEqual(result["pending"], ["Qwen/Qwen3.8-27B"])
        after = self.client.post("/api/updater/decision", headers=LOCAL,
                                 json={"ids": ["Qwen/Qwen3.8-27B"], "decision": "decline", "remember": True}).json()
        self.assertFalse(after["notify"])
        status = self.client.get("/api/updater/status", headers=LOCAL).json()
        self.assertEqual(status["candidates"][0]["remembered"], "decline")
        self.assertIn("sources", status)
        self.assertFalse(status["credentials"]["runpod_api_key"])

    def test_bad_decision_is_a_400_not_a_crash(self):
        response = self.client.post("/api/updater/decision", headers=LOCAL, json={"ids": [], "decision": "maybe"})
        self.assertEqual(response.status_code, 400)

    def test_search_filters(self):
        data = self.client.get("/api/updater/search", headers=LOCAL,
                               params={"q": "Qwen", "dense": "true", "min_b": 27, "max_b": 32}).json()
        self.assertEqual({r["id"] for r in data["results"]}, {"Qwen/Qwen3.8-27B", "Qwen/Qwen3.6-27B"})
        newer = self.client.get("/api/updater/search", headers=LOCAL, params={"newer": "true", "dense": "true"}).json()
        self.assertEqual([r["id"] for r in newer["results"]], ["Qwen/Qwen3.8-27B"])

    def test_install_and_paid_training_need_confirmation(self):
        response = self.client.post("/api/updater/install", headers=LOCAL, json={"plan_id": "nope", "confirm": True})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/updater/train", headers=LOCAL, json={"spec": {}, "confirm": None})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
