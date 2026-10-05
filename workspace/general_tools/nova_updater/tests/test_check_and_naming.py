# Last updated: 2026-10-05 21:33:05
# @nova: Tests model-name parsing and the startup update check: candidates, remembered decisions, caching and offline behaviour.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v"""
import unittest

from support import FakeSource, Workspace, hit  # noqa: F401  (support sets sys.path)
from nova_updater import check, current, naming, store


class Naming(unittest.TestCase):
    def test_qwen_names(self):
        n = naming.parse("Qwen/Qwen3.8-27B")
        self.assertEqual((n.family, n.version, n.size_b, n.dense_chat, n.slug), ("Qwen", (3, 8), 27.0, True, "qwen3.8"))
        moe = naming.parse("Qwen/Qwen3-30B-A3B-Instruct-2507")
        self.assertTrue(moe.moe)
        self.assertEqual(moe.revision, "2507")
        self.assertTrue(naming.parse("Qwen/Qwen3.6-27B-FP8").quantized)
        self.assertTrue(naming.parse("Qwen/Qwen2.5-32B-Instruct").dense_chat)
        self.assertEqual(naming.parse("Qwen/QwQ-32B").family, "QwQ")
        self.assertIsNone(naming.parse("Qwen/Qwen3.8-Flash-Next"))

    def test_versions(self):
        cur = naming.parse("Qwen3.6-27B")
        self.assertTrue(naming.is_newer(naming.parse("Qwen/Qwen3.8-27B"), cur))
        self.assertFalse(naming.is_newer(naming.parse("Qwen/Qwen3-32B"), cur))
        self.assertFalse(naming.is_newer(naming.parse("Qwen/QwQ-32B"), cur))
        self.assertTrue(naming.is_newer(naming.parse("Qwen/Qwen3.6-27B-2609"), cur))

    def test_gguf_file_names(self):
        info = naming.parse_gguf_filename("models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        self.assertEqual((info["quant"], info["model"]["repo"]), ("UD-Q6_K_XL", "Qwen3.6-27B"))
        self.assertTrue(naming.parse_gguf_filename("mmproj-F16.gguf")["mmproj"])
        split = naming.parse_gguf_filename("Qwen3.8-27B-Q8_0-00001-of-00002.gguf")
        self.assertEqual((split["quant"], split["part"], split["parts"]), ("Q8_0", 1, 2))


HITS = [hit("Qwen/Qwen3.8-27B", 27_781_427_952), hit("Qwen/Qwen3.8-27B-FP8", 27_782_935_472),
        hit("Qwen/Qwen3.6-27B", 27_781_427_952, created="2026-04-21T00:00:00Z"),
        hit("Qwen/Qwen3.8-30B-A3B", 30_500_000_000), hit("Qwen/Qwen3.9-32B", 32_800_000_000, license="other"),
        hit("Qwen/Qwen4-72B", 72_000_000_000), hit("Qwen/Qwen3.8-27B-Base", 27_781_427_952)]


class StartupCheck(Workspace):
    def test_reads_the_running_model_from_the_launcher(self):
        model = current.active_model()
        self.assertEqual(model["model_path"], "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        self.assertEqual((model["label"], model["quant"], model["publisher_hint"]), ("Qwen3.6-27B", "UD-Q6_K_XL", "unsloth"))
        self.boot("active_model.txt", "models\\qwen3.8\\Qwen3.8-27B-UD-Q6_K_XL.gguf\r\n")
        self.boot("active_mmproj.txt", "none\r\n")
        model = current.active_model()
        self.assertEqual((model["label"], model["mmproj_path"], model["source"]), ("Qwen3.8-27B", None, "boot file"))

    def test_only_dense_newer_permissive_same_size_class(self):
        result = check.run_check(force=True, src=FakeSource(HITS))
        self.assertEqual([c["id"] for c in result["candidates"]], ["Qwen/Qwen3.8-27B"])
        self.assertTrue(result["notify"])
        self.assertEqual(result["candidates"][0]["version"], "3.8")

    def test_remembered_decline_silences_that_version_only(self):
        check.run_check(force=True, src=FakeSource(HITS))
        after = check.record_decision(["Qwen/Qwen3.8-27B"], "decline", remember=True)
        self.assertFalse(after["notify"])
        self.assertEqual(after["candidates"][0]["remembered"], "decline")
        newer = HITS + [hit("Qwen/Qwen3.9-27B", 27_900_000_000)]
        result = check.run_check(force=True, src=FakeSource(newer))
        self.assertEqual(result["pending"], ["Qwen/Qwen3.9-27B"])

    def test_decline_without_remember_only_lasts_this_session(self):
        check.run_check(force=True, src=FakeSource(HITS))
        self.assertFalse(check.record_decision(["Qwen/Qwen3.8-27B"], "decline", remember=False)["notify"])
        check._session_declined.clear()  # a new Nova Chat start
        self.assertTrue(check.status()["notify"])

    def test_status_uses_fresh_boot_configuration_without_rewriting_cached_comparison(self):
        check.run_check(force=True, src=FakeSource(HITS))
        before = store.load()
        self.boot("active_model.txt", "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf")
        result = check.status()
        self.assertEqual(result["current"]["label"], "Qwen3.8-27B")
        self.assertEqual(result["current"]["source"], "boot file")
        self.assertEqual(result["checked_current"]["label"], "Qwen3.6-27B")
        self.assertTrue(result["catalog_stale"])
        self.assertFalse(result["notify"])
        self.assertEqual(result["pending"], [])
        self.assertEqual(store.load(), before)

    def test_cache_means_one_request_per_ttl(self):
        source = FakeSource(HITS)
        check.run_check(force=True, src=source)
        check.run_check(src=source)
        self.assertEqual(source.searches, 1)

    def test_offline_never_raises_and_keeps_last_answer(self):
        check.run_check(force=True, src=FakeSource(HITS))
        result = check.run_check(force=True, src=FakeSource(fail="no network"))
        self.assertEqual(result["state"], "offline")
        self.assertEqual([c["id"] for c in result["candidates"]], ["Qwen/Qwen3.8-27B"])
        self.assertFalse(result["notify"])

    def test_unknown_running_model_is_reported_not_guessed(self):
        (self.ws / "start_llama_qwen36.cmd").unlink()
        self.assertEqual(check.run_check(force=True, src=FakeSource(HITS))["state"], "unknown-current")


if __name__ == "__main__":
    unittest.main()
