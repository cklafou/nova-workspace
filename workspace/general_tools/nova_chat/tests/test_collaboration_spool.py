# @nova: Verify Cowork shared-folder delivery, crash recovery and bounded replay using disposable collaboration stores.
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from general_tools.nova_chat.collaboration import CollaborationStore, SpoolBridge


class SpoolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = CollaborationStore(self.base / "store")
        self.bridge = SpoolBridge(self.store, self.base / "shared")

    def request(self, action="send", **values):
        request_id = str(uuid.uuid4())
        source = self.bridge.requests / (request_id + ".json")
        temporary = source.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"id": request_id, "action": action, **values}), encoding="utf-8")
        os.replace(temporary, source)
        return source

    def reply(self, source):
        return json.loads((self.bridge.replies / source.name).read_text(encoding="utf-8"))

    def test_partial_temp_is_ignored_until_atomic_publish(self):
        request_id = str(uuid.uuid4())
        partial = self.bridge.requests / (request_id + ".json.tmp")
        partial.write_text('{"id":', encoding="utf-8")
        self.bridge.process()
        self.assertTrue(partial.exists())
        self.assertEqual(self.store.events(0)["events"], [])
        partial.write_text(json.dumps({"id": request_id, "action": "send", "text": "Ready"}), encoding="utf-8")
        source = partial.with_suffix("")
        os.replace(partial, source)
        self.bridge.process()
        self.assertTrue(self.reply(source)["ok"])
        self.assertFalse(source.exists())
        self.assertEqual(self.store.events(0)["events"][0]["text"], "Ready")

    def test_ack_is_atomic_and_persisted_before_request_delete(self):
        source = self.request(text="Persist before acknowledgment")
        target = self.bridge.replies / source.name
        original_replace, original_unlink = os.replace, Path.unlink
        order = []
        def replace(old, new):
            self.assertEqual(Path(new), target)
            self.assertTrue(source.exists())
            self.assertEqual(len(self.store.events(0)["events"]), 1)
            self.assertEqual(Path(old).parent, target.parent)
            result = original_replace(old, new)
            order.append("ack")
            return result
        def unlink(path, *args, **kwargs):
            if path == source:
                self.assertTrue(target.exists())
                self.assertTrue(self.reply(source)["ok"])
                order.append("delete")
            return original_unlink(path, *args, **kwargs)
        with patch("general_tools.nova_chat.collaboration.os.replace", side_effect=replace), patch.object(Path, "unlink", new=unlink):
            self.bridge.process()
        self.assertEqual(order, ["ack", "delete"])

    def test_failed_ack_write_recovers_without_duplicate_message(self):
        source = self.request(text="One durable message", client_message_id="retry-after-crash")
        with patch("general_tools.nova_chat.collaboration.os.replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.bridge.process()
        self.assertTrue(source.exists())
        self.assertFalse((self.bridge.replies / source.name).exists())
        self.assertEqual(len(self.store.events(0)["events"]), 1)
        restarted = SpoolBridge(CollaborationStore(self.base / "store"), self.base / "shared")
        restarted.process()
        self.assertTrue(self.reply(source)["ok"])
        self.assertFalse(source.exists())
        retried = self.request(text="One durable message", client_message_id="retry-after-crash")
        restarted.process()
        self.assertEqual(self.reply(retried)["result"]["seq"], self.reply(source)["result"]["seq"])
        self.assertEqual(len(self.store.events(0)["events"]), 1)

    def test_existing_ack_recovers_interrupted_request_deletion(self):
        source = self.request(text="Already accepted")
        saved = source.read_bytes()
        self.bridge.process()
        source.write_bytes(saved)
        with patch.object(self.bridge, "dispatch", side_effect=AssertionError("must reuse existing acknowledgment")):
            self.bridge.process()
        self.assertFalse(source.exists())
        self.assertTrue(self.reply(source)["ok"])
        self.assertEqual(len(self.store.events(0)["events"]), 1)

    def test_invalid_json_and_oversized_requests_fail_without_publish(self):
        for raw in ('{"incomplete":', "x" * 80001):
            with self.subTest(size=len(raw)):
                source = self.bridge.requests / (str(uuid.uuid4()) + ".json")
                source.write_text(raw, encoding="utf-8")
                self.bridge.process()
                self.assertFalse(self.reply(source)["ok"])
                self.assertFalse(source.exists())
        self.assertEqual(self.store.events(0)["events"], [])

    def test_author_fields_cannot_spoof_cole_codex_or_nova(self):
        for name in ("cole", "codex", "nova"):
            with self.subTest(name=name):
                source = self.request(text="Sender remains Cowork", participant=name, author=name, label=name)
                self.bridge.process()
                event = self.reply(source)["result"]
                self.assertEqual(event["participant"], "claude")
                self.assertEqual(event["label"], "Claude Cowork")

    def test_replay_drains_all_pages_in_order_and_keeps_cursor(self):
        for index in range(221):
            self.store.publish("codex", "Message " + str(index), str(index))
        cursor, found, sizes = 0, [], []
        while True:
            source = self.request("read", after=cursor)
            self.bridge.process()
            response = self.reply(source)
            self.assertTrue(response["ok"])
            page = response["result"]
            found.extend(page["events"])
            sizes.append(len(page["events"]))
            self.assertGreaterEqual(page["cursor"], cursor)
            cursor = page["cursor"]
            if not page["has_more"]:
                break
        self.assertEqual(sizes, [100, 100, 21])
        self.assertEqual([event["seq"] for event in found], list(range(1, 222)))
        empty = self.request("read", after=cursor)
        self.bridge.process()
        self.assertEqual(self.reply(empty)["result"], {"events": [], "cursor": 221, "has_more": False})

    def test_invalid_actions_cursors_and_identity_do_not_publish(self):
        invalid = [{"action": "delete"}, {"action": "read", "after": -1}, {"action": "read", "after": True},
                   {"action": "presence", "state": "thinking"}, {"action": "send", "text": []},
                   {"action": "send", "text": "Message", "client_message_id": []}]
        for values in invalid:
            source = self.request(**values)
            self.bridge.process()
            self.assertFalse(self.reply(source)["ok"])
        self.assertEqual(self.store.events(0)["events"], [])

    def test_drain_is_bounded_and_continues_on_next_tick(self):
        for index in range(55):
            self.request(text="Queued " + str(index))
        self.bridge.process()
        self.assertEqual(len(list(self.bridge.replies.glob("*.json"))), 50)
        self.assertEqual(len(list(self.bridge.requests.glob("*.json"))), 5)
        self.bridge.process()
        self.assertEqual(len(self.store.events(0)["events"]), 55)
        self.assertEqual(list(self.bridge.requests.glob("*.json")), [])

    def test_noncanonical_ignored_names_cannot_starve_valid_requests(self):
        for index in range(50):
            name = "00000000-0000-0000-000A-" + str(uuid.UUID(int=index + 10)).upper()[-12:]
            (self.bridge.requests / (name + ".json")).write_text("{}", encoding="utf-8")
        source = self.request(text="Still reachable")
        self.bridge.process()
        self.assertTrue((self.bridge.replies / source.name).exists())
        self.assertTrue(self.reply(source)["ok"])
        self.assertEqual(len(self.store.events(0)["events"]), 1)


    def test_expired_replies_are_pruned_without_losing_durable_history(self):
        import os
        import time
        old = self.request(text="Keep the durable conversation")
        self.bridge.process()
        target = self.bridge.replies / old.name
        os.utime(target, (time.time() - 601, time.time() - 601))
        fresh = self.request("read", after=0)
        self.bridge.process()
        self.assertFalse(target.exists())
        self.assertTrue((self.bridge.replies / fresh.name).exists())
        self.assertEqual(self.reply(fresh)["result"]["events"][0]["text"],
                         "Keep the durable conversation")
        self.assertEqual(len(self.store.events(0)["events"]), 1)


if __name__ == "__main__":
    unittest.main()
