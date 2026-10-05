# Last updated: 2026-10-06 03:10:19
# @nova: Preserve voice_fast cache mode across conversational segments while retaining reasoning for tools and factual correction.
import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
import test_witness_delivery as fixture
from test_witness_delivery import nova, Transcript, call, text_of
from nova_runtime.model_client import ModelClient
from nova_runtime.conversation import ActiveTurn


def speak(text, more=True):
    return call('speak', text=text, **{'continue': more})


class VoiceCacheModeTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixture.DeliveryTests.setUp
    fetch = fixture.DeliveryTests.fetch
    worker = fixture.DeliveryTests.worker
    execute = fixture.DeliveryTests.execute
    verify = fixture.DeliveryTests.verify

    async def run_voice(self, *, register='voice_fast', turn=None, provider_hook=None):
        modes, segments = [], []
        async def provider(messages, on_token, **kwargs):
            if not kwargs.get('preserve_messages'):
                modes.append(kwargs['enable_thinking'])
            if provider_hook is not None:
                await provider_hook(messages, kwargs)
            return await self.fetch(messages, on_token, **kwargs)
        async def noop(*args): pass
        async def segment(text, meta): segments.append((text, meta))
        async def done(text): self.done.append(text)
        async def error(text): self.errors.append(text)
        client = ModelClient(); client.register({'Nova': nova})
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            await client.generate('Nova', Transcript(), on_token=noop, on_done=done,
                                  on_error=error, on_segment=segment, steering=turn,
                                  register=register)
        await asyncio.sleep(0)
        self.assertEqual(self.errors, [])
        return modes, segments

    async def test_speak_continuation_keeps_fast_mode_without_counting_it_as_tool_work(self):
        first = 'Hello, Cole. This is a completed conversational segment that will be followed by another.'
        final = 'The remaining conversational segment completes the same greeting without external work.'
        self.generations = [speak(first), speak(final, False)]
        self.verdicts = ['PASS', 'PASS']
        modes, segments = await self.run_voice()
        self.assertEqual(modes, [False, False])
        self.assertEqual([text for text, _ in segments], [first, final])
        self.assertEqual(len(self.audit_calls), 2)
        self.assertEqual(self.tools, [])

    async def test_new_human_words_do_not_by_themselves_change_reasoning_mode(self):
        turn = ActiveTurn()
        self.generations = ['This completed conversational answer addresses the first greeting.',
                            'This second conversational answer addresses the follow-up greeting.']
        self.verdicts = ['PASS', 'PASS']
        pushed = []
        async def during_audit(messages, kwargs):
            if kwargs.get('preserve_messages') and not pushed:
                pushed.append(True)
                turn.push([{'content': 'FOLLOWUP GREETING'}])
        modes, segments = await self.run_voice(turn=turn, provider_hook=during_audit)
        self.assertEqual(modes, [False, False])
        self.assertIn('FOLLOWUP GREETING', text_of(self.main_calls[1]))
        self.assertEqual([meta['input_revision'] for _, meta in segments], [0, 1])
        self.assertEqual([meta['audit']['status'] for _, meta in segments], ['PASS', 'PASS'])

    async def test_tool_chain_still_enables_reasoning_after_the_actual_attempt(self):
        self.generations = [call('read_file', path='fixture'),
                            'The requested tool attempt completed and its actual receipt is retained.']
        self.verdicts = ['PASS']
        modes, _ = await self.run_voice()
        self.assertEqual(modes, [False, True])
        self.assertEqual(len(self.tools), 1)
        self.assertIn('fixture receipt', text_of(self.main_calls[1]))

    async def test_witness_correction_keeps_existing_deliberative_revision(self):
        self.generations = ['This initial answer contains an unsupported statement about the fixture.',
                            'The corrected answer explicitly limits itself to what the available receipt establishes.']
        self.verdicts = ['CONCERN: The first statement is unsupported by available evidence.', 'PASS']
        modes, segments = await self.run_voice()
        self.assertEqual(modes, [False, True])
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][1]['audit']['status'], 'PASS')
        self.assertEqual(len(self.audit_calls), 2)

    async def test_withheld_real_tool_proposal_preserves_reasoning_for_reconsideration(self):
        turn = ActiveTurn()
        self.generations = [call('write_file', path='obsolete-target', content='never'),
                            'I retained the original task and reconsidered the proposed action after the update.']
        self.verdicts = ['PASS']
        pushed = []
        async def during_provider(messages, kwargs):
            if not kwargs.get('preserve_messages') and not pushed:
                pushed.append(True)
                turn.push([{'content': 'Do not write that file; only explain what you would do.'}])
        modes, _ = await self.run_voice(turn=turn, provider_hook=during_provider)
        self.assertEqual(modes, [False, True])
        self.assertEqual(self.tools, [])
        self.assertIn('NOT executed', text_of(self.main_calls[1]))

    async def test_normal_voice_register_and_disabled_fast_tunable_keep_reasoning(self):
        for register in ['voice', 'text', 'voice_fast']:
            with self.subTest(register=register):
                self.config['voice_fast_thinking_off'] = False
                self.generations = ['The ordinary reasoning-enabled greeting completes with its audit intact.']
                self.verdicts = ['PASS']
                modes, segments = await self.run_voice(register=register)
                self.assertEqual(modes, [True])
                self.assertEqual(segments[0][1]['audit']['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
