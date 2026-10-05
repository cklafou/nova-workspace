# @nova: Verify useful body-owned output segments, frozen audits, total budgets, and explicit Stop without provider cancellation on input.
import asyncio
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
import test_conversation as fixture
from test_witness_delivery import nova, witness, call, text_of
from nova_runtime.conversation import ActiveTurn, cancellation_requested, observer_cancel_is_external


def speak(text, more=True):
    return call('speak', text=text, **{'continue': more})


class SegmentTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixture.ContinuationTests.setUp
    fetch = fixture.ContinuationTests.fetch
    worker = fixture.ContinuationTests.worker
    execute = fixture.ContinuationTests.execute
    verify = fixture.ContinuationTests.verify
    run_body = fixture.ContinuationTests.run_body
    collect_audit = fixture.ContinuationTests.collect_audit

    async def collect(self, text, metadata):
        self.segments.append((text, copy.deepcopy(metadata)))

    async def test_explicit_speak_delivers_before_tool_and_final_is_not_replayed(self):
        self.segments = []
        first = 'I have organized the request and will now inspect the requested fixture.'
        final = 'The requested inspection is complete and its actual receipt is available.'
        self.generations = [speak(first), call('read_file', path='fixture'), final]
        self.verdicts = ['PASS', 'PASS']
        calls_at_delivery = []
        async def segment(text, meta):
            calls_at_delivery.append(len(self.tools))
            await self.collect(text, meta)
        turn = ActiveTurn(turn_id='stable-work')
        await self.run_body(turn, on_segment=segment)
        self.assertEqual(len(self.segments), 2)
        self.assertEqual(calls_at_delivery, [0, 1])
        self.assertEqual(self.segments[0][0], first)
        self.assertIn(final, self.segments[1][0])
        self.assertEqual([m['segment_index'] for _, m in self.segments], [1, 2])
        self.assertEqual([m['final'] for _, m in self.segments], [False, True])
        self.assertEqual({m['turn_id'] for _, m in self.segments}, {'stable-work'})
        self.assertEqual(self.done, ['\n\n'.join(t for t, _ in self.segments)])
        self.assertNotIn('speak', [t[0] for t in self.tools])
        self.assertIn('preceding segment was delivered', text_of(self.main_calls[1]))

    async def test_followup_during_audit_preserves_completed_segment_and_frozen_record(self):
        self.segments = []
        first = 'The first completed answer addresses the original fixture request correctly.'
        second = 'The next completed answer addresses the additional follow-up without erasing earlier work.'
        self.generations = [first, second]
        self.verdicts = ['PASS', 'PASS']
        turn = ActiveTurn(turn_id='frozen-work')
        human = ['ORIGINAL HUMAN INPUT']
        base_fetch = self.fetch
        audit_prompts = []
        async def provider(messages, token, **kwargs):
            if kwargs.get('preserve_messages'):
                audit_prompts.append(text_of(messages))
                if len(audit_prompts) == 1:
                    turn.push([{'content': 'FOLLOWUP INPUT'}])
                    human[0] = 'FOLLOWUP HUMAN INPUT'
                    await asyncio.sleep(0)
            return await base_fetch(messages, token, **kwargs)
        with patch.object(witness, 'human_record', side_effect=lambda: human[0]), \
             patch.object(witness, 'wire_record', side_effect=lambda: human[0]), \
             patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            await self.run_body(turn, on_segment=self.collect)
        self.assertEqual([text for text, _ in self.segments], [first, second])
        self.assertEqual([meta['input_revision'] for _, meta in self.segments], [0, 1])
        self.assertEqual([meta['audit']['input_revision'] for _, meta in self.segments], [0, 1])
        self.assertIn('ORIGINAL HUMAN INPUT', audit_prompts[0])
        self.assertNotIn('FOLLOWUP HUMAN INPUT', audit_prompts[0])
        self.assertIn('FOLLOWUP HUMAN INPUT', audit_prompts[1])
        self.assertIn('FOLLOWUP INPUT', text_of(self.main_calls[1]))
        self.assertIn(first, text_of(self.main_calls[1]))
        self.assertIn('explicitly reconcile or correct', text_of(self.main_calls[1]))

    async def test_concern_on_segment_two_does_not_erase_segment_one(self):
        self.segments = []
        first = 'The first segment is complete and independently supported by the current fixture.'
        wrong = 'The second segment incorrectly claims that the fixture contained a verified result.'
        fixed = 'The second segment is corrected: the available fixture does not establish that result.'
        self.generations = [speak(first), wrong, fixed]
        self.verdicts = ['PASS', 'CONCERN: The second claim is unsupported by the fixture.', 'PASS']
        await self.run_body(ActiveTurn(), on_segment=self.collect)
        self.assertEqual([text for text, _ in self.segments], [first, fixed])
        self.assertEqual(self.done, [first + '\n\n' + fixed])
        self.assertNotIn(wrong, self.done[0])

    async def test_stop_retains_delivered_segment_and_withholds_inflight_output(self):
        self.segments = []
        first = 'This useful completed segment is delivered before the next work step starts.'
        self.generations = [speak(first)]
        self.verdicts = ['PASS']
        started = asyncio.Event()
        base_fetch = self.fetch
        async def provider(messages, token, **kwargs):
            if not kwargs.get('preserve_messages') and self.segments:
                started.set()
                await asyncio.Event().wait()
            return await base_fetch(messages, token, **kwargs)
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            task = asyncio.create_task(self.run_body(ActiveTurn(), on_segment=self.collect))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual([text for text, _ in self.segments], [first])
        self.assertEqual(self.done, [])

    async def test_empty_speak_and_continue_false_end_without_extra_inference(self):
        for text in ['', 'A final segment with no further work remains in the completed transcript.']:
            with self.subTest(text=bool(text)):
                self.segments = []
                self.done.clear()
                self.generations = [speak(text, more=False)]
                self.verdicts = ['PASS'] if text else []
                self.main_calls.clear()
                await self.run_body(ActiveTurn(), on_segment=self.collect)
                self.assertEqual(len(self.main_calls), 1)
                self.assertEqual(self.done, [text])
                self.assertEqual([t for t, _ in self.segments], [text] if text else [])

    async def test_pending_input_does_not_replenish_tool_budget(self):
        self.config['max_tool_loops'] = 1
        self.segments = []
        self.generations = [speak('This first work segment is complete, but further work has not yet happened.')]
        self.verdicts = ['PASS']
        turn = ActiveTurn()
        async def segment(text, meta):
            await self.collect(text, meta)
            if meta['segment_index'] == 1:
                turn.push([{'content': 'Another follow-up must not reset the total work allowance.'}])
        await self.run_body(turn, on_segment=segment)
        self.assertEqual(len(self.main_calls), 1)
        self.assertEqual(turn.applied_revision, 1)
        self.assertIn('not complete', self.segments[-1][0])
        self.assertEqual(self.segments[-1][1]['audit']['status'], 'NOT_RUN')
        self.assertEqual(len(self.done), 1)

    async def test_budget_terminal_seals_before_observer_can_admit_stranded_input(self):
        self.config['max_tool_loops'] = 1
        self.segments = []
        self.generations = [speak('A completed progress segment is delivered before the work allowance ends.')]
        self.verdicts = ['PASS']
        turn = ActiveTurn()
        late_admissions = []
        async def audit(metadata):
            if metadata['status'] == 'NOT_RUN':
                late_admissions.append(turn.push([{'content': 'This must become a next run.'}]))
        await self.run_body(turn, on_audit=audit, on_segment=self.collect)
        self.assertEqual(late_admissions, [False])
        self.assertEqual(len(self.done), 1)
        self.assertFalse(turn.pending)
        self.assertFalse(turn.can_accept)

    async def test_witness_revision_allowance_is_shared_across_segments(self):
        self.config['witness_max_rounds'] = 1
        self.segments = []
        first = 'The first proposed segment contains a claim that the witness asks Nova to correct.'
        corrected = 'The first segment is now corrected and the remaining work continues afterward.'
        second = 'The second segment still contains a disputed claim at the total revision limit.'
        self.generations = [speak(first), speak(corrected), second]
        self.verdicts = ['CONCERN: Correct the first unsupported claim.', 'PASS',
                         'CONCERN: The second disputed claim remains unsupported.']
        await self.run_body(ActiveTurn(), on_segment=self.collect)
        self.assertEqual(len(self.main_calls), 3)
        self.assertEqual([t for t, _ in self.segments], [corrected, second])
        self.assertEqual(self.segments[0][1]['audit']['status'], 'PASS')
        self.assertEqual(self.segments[1][1]['audit']['status'], 'CONCERN')
        self.assertNotEqual(self.segments[1][1]['audit']['status'], 'PASS')

    async def test_segment_control_is_optional_for_legacy_clients(self):
        self.generations = ['A normal final answer still uses the original single-delivery callback.']
        self.verdicts = ['PASS']
        await self.run_body(ActiveTurn())
        self.assertEqual(len(self.done), 1)
        self.assertNotIn('CONVERSATION WORK LOOP:', text_of(self.main_calls[0]))


class CompatibilityTests(unittest.TestCase):
    def test_python310_style_task_has_no_cancelling_attribute(self):
        task = types.SimpleNamespace(cancelled=lambda: False, _must_cancel=False)
        self.assertFalse(cancellation_requested(task))
        task._must_cancel = True
        self.assertTrue(cancellation_requested(task))
        task._must_cancel = False
        self.assertTrue(observer_cancel_is_external(task))

    def test_explicit_snapshot_never_reloads_mutating_body_records(self):
        snapshot = {'session_tools': 'FROZEN TOOL', 'spoken': 'FROZEN ROOM', 'humans': 'FROZEN HUMAN'}
        with patch.object(witness, 'session_tool_record', side_effect=AssertionError('must not reload')), \
             patch.object(witness, 'wire_record', side_effect=AssertionError('must not reload')), \
             patch.object(witness, 'human_record', side_effect=AssertionError('must not reload')):
            for budget in [3, 2, 1, 0]:
                messages = witness.build_witness('A fixed candidate.', [], reads_remaining=budget,
                                                  evidence_snapshot=snapshot)
                text = text_of(messages)
                for value in snapshot.values():
                    self.assertIn(value, text)
                self.assertIn(f'READ BUDGET: {budget}', text)


if __name__ == '__main__':
    unittest.main()
