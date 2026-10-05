# @nova: Verify isolated model-client register routing, optional audit sinks and concurrent-request compatibility.
import asyncio
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_runtime.model_client import ModelClient, normalize_register


class RegisterTests(unittest.TestCase):
    def test_exact_supported_registers_and_malformed_values(self):
        for value in ("text", "voice", "voice_fast"):
            self.assertEqual(normalize_register(value), value)
        for value in (None, "", "VOICE", " voice", "voice ", "voice-fast", "other",
                      False, 1, [], {}, ["voice"], {"register": "voice"}):
            with self.subTest(value=value):
                self.assertEqual(normalize_register(value), "text")


class ModelClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = ModelClient()
        self.transcript = object()
        self.sinks = {key: AsyncMock() for key in ("on_token", "on_done", "on_error")}

    async def test_nova_receives_normalized_register_and_existing_options(self):
        stream = AsyncMock()
        self.client.register({"Nova": types.SimpleNamespace(stream_response=stream)})
        images = [{"fixture": "image metadata only"}]
        for value, expected in (("voice", "voice"), ("voice_fast", "voice_fast"),
                                ({"bad": "value"}, "text")):
            await self.client.generate("Nova", self.transcript, **self.sinks, register=value,
                                       workspace_context="fixture context", images=images,
                                       autonomous=True, temperature=0.4, top_p=0.8)
            args, kwargs = stream.await_args
            self.assertIs(args[0], self.transcript)
            self.assertEqual(kwargs["register"], expected)
            self.assertEqual(kwargs["workspace_context"], "fixture context")
            self.assertIs(kwargs["images"], images)
            self.assertTrue(kwargs["autonomous"])
            self.assertEqual((kwargs["temperature"], kwargs["top_p"]), (0.4, 0.8))
            self.assertNotIn("on_audit", kwargs)

    async def test_default_and_none_audit_work_with_client_without_audit_parameter(self):
        seen = []
        async def old_nova(transcript, on_token, on_done, on_error, *,
                           on_think_token, on_progress, on_tool_executed,
                           workspace_context, images, autonomous, temperature, top_p,
                           register="text"):
            seen.append(register)
            await on_done("delivered fixture")
        self.client.register({"Nova": types.SimpleNamespace(stream_response=old_nova)})
        await self.client.generate("Nova", self.transcript, **self.sinks)
        await self.client.generate("Nova", self.transcript, **self.sinks, on_audit=None)
        self.assertEqual(seen, ["text", "text"])
        self.assertEqual(self.sinks["on_done"].await_count, 2)

    async def test_audit_callback_is_forwarded_unchanged_only_when_present(self):
        audit = AsyncMock()
        report = {"status": "INCOMPLETE", "reason": "fixture evidence unavailable"}
        async def stream(*args, **kwargs):
            self.assertIs(kwargs["on_audit"], audit)
            await kwargs["on_audit"](report)
            await args[2]("delivered but unapproved fixture")
        self.client.register({"Nova": types.SimpleNamespace(stream_response=stream)})
        await self.client.generate("Nova", self.transcript, **self.sinks,
                                   register="voice", on_audit=audit)
        audit.assert_awaited_once_with(report)
        self.sinks["on_done"].assert_awaited_once_with("delivered but unapproved fixture")

    async def test_legacy_client_gets_no_register_or_audit_keywords(self):
        calls = []
        async def legacy(transcript, on_token, on_done, on_error, *, workspace_context, images):
            calls.append((transcript, workspace_context, images))
            await on_done("legacy fixture")
        self.client.register({"Legacy": types.SimpleNamespace(stream_response=legacy)})
        audit = AsyncMock()
        await self.client.generate("Legacy", self.transcript, **self.sinks,
                                   workspace_context="context", register="voice", on_audit=audit)
        self.assertEqual(calls, [(self.transcript, "context", None)])
        audit.assert_not_awaited()
        self.sinks["on_done"].assert_awaited_once_with("legacy fixture")

    async def test_gemini_runner_keeps_existing_call_signature(self):
        calls = []
        async def gemini(on_token, on_done, on_error, workspace_context, *, images):
            calls.append((on_token, workspace_context, images))
            await on_done("gemini fixture")
        self.client.register(gemini_runner=gemini)
        audit = AsyncMock()
        await self.client.generate("Gemini", self.transcript, **self.sinks,
                                   workspace_context="context", register="voice_fast", on_audit=audit)
        self.assertEqual(calls, [(self.sinks["on_token"], "context", None)])
        audit.assert_not_awaited()
        self.sinks["on_done"].assert_awaited_once_with("gemini fixture")

    async def test_concurrent_calls_keep_registers_and_callbacks_independent(self):
        both_entered = asyncio.Event()
        entered = []
        audits = {name: AsyncMock() for name in ("voice", "voice_fast")}
        done = {name: AsyncMock() for name in audits}
        async def stream(transcript, on_token, on_done, on_error, *, register, on_audit, **kwargs):
            entered.append(transcript)
            if len(entered) == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=1)
            self.assertEqual(register, transcript)
            self.assertIs(on_audit, audits[transcript])
            await on_audit({"status": "PASS", "fixture": transcript})
            await on_done(transcript)
        self.client.register({"Nova": types.SimpleNamespace(stream_response=stream)})
        await asyncio.gather(*(self.client.generate(
            "Nova", name, on_token=AsyncMock(), on_done=done[name], on_error=AsyncMock(),
            register=name, on_audit=audits[name]) for name in audits))
        for name in audits:
            audits[name].assert_awaited_once_with({"status": "PASS", "fixture": name})
            done[name].assert_awaited_once_with(name)


if __name__ == "__main__":
    unittest.main()
