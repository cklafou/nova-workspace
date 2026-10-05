# @nova: Verify body-owned non-cancelling continuation, request anchors, audit revisions, sealing, and relocation.
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_runtime.conversation import ActiveTurn, ConversationTurns, ANCHOR, provider_messages
from nova_runtime.model_client import ModelClient
from nova_cortex.context_budget import anchor_current_request, fit_messages, text_size
import test_witness_delivery as delivery_fixture
from test_witness_delivery import Transcript, text_of, call, nova, witness, operations


class InboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_revision_observer_reentrancy_and_seal(self):
        seen = []
        owner = object()
        async def applied(batch, revision):
            seen.append((batch, revision))
            if revision == 1:
                turn.push([{'content': 'during observer'}])
        manager = ConversationTurns()
        turn = manager.begin('room', turn_id='same-run', on_apply=applied)
        self.assertTrue(manager.submit('room', [{'content': 'first', 'owner': owner}, {'content': 'second'}]))
        self.assertFalse(turn.try_seal())
        batch, revision = await turn.consume()
        self.assertEqual([e['content'] for e in batch], ['first', 'second'])
        self.assertIs(batch[0]['owner'], owner)
        self.assertEqual(revision, 1)
        self.assertTrue(turn.pending)
        await turn.consume()
        self.assertEqual(turn.applied_revision, 2)
        self.assertTrue(turn.try_seal())
        self.assertFalse(manager.submit('room', [{'content': 'late'}]))
        replacement = manager.begin('room', turn_id='next-run')
        self.assertEqual(manager.end('room', turn), [])
        self.assertIs(manager.get('room'), replacement)
        self.assertEqual(replacement.turn_id, 'next-run')

    async def test_batch_validation_is_atomic_and_content_is_copied(self):
        turn = ActiveTurn()
        with self.assertRaises(ValueError):
            turn.push([{'content': 'valid'}, {'role': 'system', 'content': 'invalid'}])
        self.assertFalse(turn.pending)
        self.assertEqual(turn.revision, 0)
        content = [{'type': 'text', 'text': 'original'}]
        turn.push([{'content': content}])
        content[0]['text'] = 'changed externally'
        pending = turn.close()
        self.assertEqual(pending[0]['content'][0]['text'], 'original')
        self.assertFalse(turn.can_accept)

    async def test_disconnected_observer_cannot_drop_or_mutate_accepted_input(self):
        async def broken(batch, revision):
            batch[0]['content'] = 'observer mutation'
            raise ConnectionError('detached face')
        turn = ActiveTurn(on_apply=broken)
        turn.push([{'content': 'accepted input'}])
        batch, revision = await turn.consume()
        self.assertEqual(batch[0]['content'], 'accepted input')
        self.assertEqual(revision, 1)
        self.assertEqual(turn.last_observer_error, 'ConnectionError')
        async def isolated_cancel(*args): raise asyncio.CancelledError()
        turn.on_apply = isolated_cancel
        turn.push([{'content': 'second input'}])
        batch, _ = await turn.consume()
        self.assertEqual(batch[0]['content'], 'second input')
        self.assertEqual(turn.last_observer_error, 'CancelledError')

    async def test_apply_observer_cannot_swallow_explicit_stop(self):
        async def cancelling_observer(*args):
            asyncio.current_task().cancel()
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                pass
        turn = ActiveTurn(on_apply=cancelling_observer)
        turn.push([{'content': 'accepted input'}])
        task = asyncio.create_task(turn.consume())
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_request_anchors_survive_fitting_and_fail_explicitly_on_overflow(self):
        messages = [{'role': 'system', 'content': 'S' * 35000},
                    {'role': 'user', 'content': 'Cole → you: ORIGINAL OBJECTIVE'},
                    {'role': 'assistant', 'content': 'old' * 5000}]
        anchor_current_request(messages)
        messages.extend([{'role': 'user', 'content': word * 500, ANCHOR: True}
                         for word in ['FOLLOWUP ONE ', 'FOLLOWUP TWO ']])
        messages.append({'role': 'user', 'content': '[System Result from read_file] ' + 'r' * 9000})
        fitted = fit_messages(messages, max_chars=18000, per_message=30)
        self.assertLessEqual(text_size(fitted), 18000)
        for original in messages:
            if original.get(ANCHOR):
                self.assertIn(original, fitted)
        with self.assertRaisesRegex(ValueError, 'none were silently discarded'):
            fit_messages(messages, max_chars=100)
        self.assertTrue(all(ANCHOR not in m for m in provider_messages(fitted)))


class ContinuationTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the established isolated body harness without inheriting/duplicating its tests.
    setUp = delivery_fixture.DeliveryTests.setUp
    worker = delivery_fixture.DeliveryTests.worker
    execute = delivery_fixture.DeliveryTests.execute
    verify = delivery_fixture.DeliveryTests.verify
    fetch = delivery_fixture.DeliveryTests.fetch
    collect_audit = delivery_fixture.DeliveryTests.collect_audit

    async def run_body(self, turn, *, on_audit=None, on_segment=None):
        async def noop(*args): pass
        async def done(value): self.done.append(value)
        async def error(value): self.errors.append(value)
        client = ModelClient()
        client.register({'Nova': nova})
        await client.generate('Nova', Transcript(), on_token=noop, on_done=done,
                              on_error=error, steering=turn, on_audit=on_audit, on_segment=on_segment)
        await asyncio.sleep(0)
        self.assertEqual(self.errors, [])

    async def test_provider_finishes_naturally_and_obsolete_proposal_is_not_executed(self):
        manager = ConversationTurns()
        applied = []
        async def accept(batch, revision): applied.extend(batch)
        turn = manager.begin('room', turn_id='same-run', on_apply=accept)
        started, release = asyncio.Event(), asyncio.Event()
        completed = []
        final = 'I retained the original task and both updates before answering with current information.'
        self.generations = [final]
        self.verdicts = ['PASS']
        base_fetch = self.fetch
        async def provider(messages, on_token, **kwargs):
            if not completed and not kwargs.get('preserve_messages'):
                started.set()
                await release.wait()
                completed.append('natural output completed')
                return call('computer_exec', command='OBSOLETE ACTION')
            return await base_fetch(messages, on_token, **kwargs)
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            task = asyncio.create_task(self.run_body(turn))
            await asyncio.wait_for(started.wait(), 2)
            manager.submit('room', [{'content': 'FOLLOWUP ONE', 'request_id': 'a'},
                                    {'content': 'FOLLOWUP TWO', 'request_id': 'b'}])
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(completed, [])
            release.set()
            await asyncio.wait_for(task, 3)
        self.assertEqual(completed, ['natural output completed'])
        self.assertEqual(self.tools, [])
        prompt = text_of(self.main_calls[0])
        self.assertIn('Explain what the visible desktop actually shows.', prompt)
        self.assertLess(prompt.index('FOLLOWUP ONE'), prompt.index('FOLLOWUP TWO'))
        self.assertIn('OBSOLETE ACTION', prompt)
        self.assertIn('NOT executed', prompt)
        self.assertEqual(self.done, [final])
        self.assertEqual(turn.turn_id, 'same-run')
        self.assertFalse(turn.can_accept)
        self.assertEqual([e['request_id'] for e in applied], ['a', 'b'])

    async def test_three_followups_during_tool_preserve_receipt_without_replay(self):
        manager = ConversationTurns()
        turn = manager.begin('room', turn_id='same-run')
        started, release = asyncio.Event(), asyncio.Event()
        original_worker = self.worker
        async def worker(fn, *args, **kwargs):
            started.set()
            await release.wait()
            return await original_worker(fn, *args, **kwargs)
        self.generations = [call('read_file', path='fixture-only'),
            'The completed tool receipt remains available alongside all three follow-up messages.']
        self.verdicts = ['PASS']
        with patch.object(operations, 'run_in_worker', side_effect=worker):
            task = asyncio.create_task(self.run_body(turn))
            await asyncio.wait_for(started.wait(), 2)
            for i in range(3):
                self.assertTrue(manager.submit('room', [{'content': f'FOLLOWUP {i}'}]))
            self.assertFalse(task.done())
            release.set()
            await asyncio.wait_for(task, 3)
        self.assertEqual(len(self.tools), 1)
        prompt = text_of(self.main_calls[1])
        self.assertIn('fixture receipt', prompt)
        self.assertIn('Explain what the visible desktop actually shows.', prompt)
        self.assertEqual([prompt.index(f'FOLLOWUP {i}') for i in range(3)],
                         sorted(prompt.index(f'FOLLOWUP {i}') for i in range(3)))
        self.assertEqual(len(self.done), 1)
        pressured = fit_messages(self.main_calls[1], max_chars=1800, per_message=40)
        pressure_text = text_of(pressured)
        self.assertLessEqual(text_size(pressured), 1800)
        self.assertIn('[System Completed Tool Attempt]', pressure_text)
        self.assertIn(self.tools[0][2], pressure_text)
        self.assertIn('observation_sha256', pressure_text)
        self.assertIn('does not mean the action did not run', pressure_text)
        self.assertNotIn('fixture receipt', pressure_text)  # raw detail can go, completed action cannot
        self.assertIn('Explain what the visible desktop actually shows.', pressure_text)
        for i in range(3):
            self.assertIn(f'FOLLOWUP {i}', pressure_text)
        tool_events = [e for e in self.events if e['stage'].startswith('tool_')]
        self.assertEqual({e['run_id'] for e in tool_events}, {'fixture-run'})

    async def test_followup_during_audit_discards_stale_verdict_and_requested_read(self):
        turn = ActiveTurn(turn_id='audit-run')
        started, release = asyncio.Event(), asyncio.Event()
        self.generations = ['The first draft claims something about an earlier request before the update.',
                            'The revised draft incorporates the newer request and keeps the original objective.']
        self.verdicts = ['PASS']
        base_fetch = self.fetch
        audit_count = 0
        async def provider(messages, token, **kwargs):
            nonlocal audit_count
            if kwargs.get('preserve_messages'):
                audit_count += 1
                if audit_count == 1:
                    started.set()
                    await release.wait()
                    return call('read_file', path='obsolete-audit-read')
            return await base_fetch(messages, token, **kwargs)
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            task = asyncio.create_task(self.run_body(turn, on_audit=self.collect_audit))
            await asyncio.wait_for(started.wait(), 2)
            turn.push([{'content': 'NEW INPUT invalidates the pending audit'}])
            release.set()
            await asyncio.wait_for(task, 3)
        self.assertEqual(self.reads, [])
        self.assertEqual(len(self.done), 1)
        self.assertIn('revised draft', self.done[0])
        self.assertEqual(self.delivery_audits[0]['input_revision'], 1)
        self.assertEqual(self.delivery_audits[0]['turn_id'], 'audit-run')
        self.assertEqual(sum(e['stage'] == 'witness_pass' for e in self.events), 1)

    async def test_observer_disconnect_does_not_interrupt_body_continuation(self):
        async def failed_observer(*args): raise ConnectionError('face detached')
        turn = ActiveTurn(on_apply=failed_observer)
        turn.push([{'content': 'Follow-up accepted before the face disconnected'}])
        self.generations = ['The body continues with the accepted input even though the face observer disconnected.']
        self.verdicts = ['PASS']
        await self.run_body(turn)
        self.assertIn('face disconnected', text_of(self.main_calls[0]))
        self.assertEqual(len(self.done), 1)
        self.assertEqual(turn.last_observer_error, 'ConnectionError')

    async def test_audit_observer_input_is_applied_before_final_seal(self):
        turn = ActiveTurn()
        self.generations = ['A first complete answer is ready but its observer receives a follow-up.',
                            'A second complete answer now addresses the follow-up in the same turn.']
        self.verdicts = ['PASS', 'PASS']
        called = []
        async def observer(metadata):
            called.append(metadata)
            if len(called) == 1:
                turn.push([{'content': 'Input at the final observer boundary'}])
        await self.run_body(turn, on_audit=observer)
        self.assertEqual(len(self.done), 1)
        self.assertIn('second complete', self.done[0])
        self.assertFalse(turn.can_accept)

    async def test_explicit_stop_still_cancels_provider_and_delivers_nothing(self):
        turn = ActiveTurn()
        started = asyncio.Event()
        cancelled = []
        async def provider(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            task = asyncio.create_task(self.run_body(turn))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(cancelled, [True])
        self.assertEqual(self.done, [])

    async def test_loop_limit_callback_followup_does_not_reset_allowance(self):
        self.config['max_tool_loops'] = 1
        turn = ActiveTurn()
        self.generations = [call(), 'The continued final answer uses the prior completed tool receipt.']
        self.verdicts = ['PASS']
        callbacks = []
        async def observer(metadata):
            callbacks.append(metadata)
            if len(callbacks) == 1:
                turn.push([{'content': 'Continue with that receipt, and answer this update.'}])
        await self.run_body(turn, on_audit=observer)
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(len(self.done), 1)
        self.assertIn('ran out of thinking room', self.done[0])
        self.assertEqual(len(self.main_calls), 1)
        self.assertEqual(turn.applied_revision, 1)


class RelocatedBodyTests(unittest.TestCase):
    def test_actual_body_continues_without_chat_face_after_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'plucked_body'
            target.mkdir()
            # Copy code only: no identity, memory, logs, credentials, models or state.
            for package in ['nova_runtime', 'nova_voice', 'nova_cortex', 'nova_logs']:
                for source in (BODY / package).rglob('*.py'):
                    if '__pycache__' in source.parts:
                        continue
                    dest = target / source.relative_to(BODY)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
            shutil.copyfile(BODY / 'nova_paths.py', target / 'nova_paths.py')
            tests = target / 'tests'
            tests.mkdir()
            for name in ['test_conversation.py', 'test_witness_delivery.py', 'test_conversation_segments.py',
                         'test_autonomy_boundaries.py', 'test_work_owner.py']:
                shutil.copyfile(BODY / 'tests' / name, tests / name)
            env = dict(os.environ, PYTHONPATH=str(target) + os.pathsep + str(tests),
                       NOVA_BODY=str(target), NOVA_WORKSPACE=str(target.parent))
            code = "import sys, pathlib, unittest; import test_conversation as t; " + \
                   "assert pathlib.Path(t.nova.__file__).is_relative_to(pathlib.Path.cwd()); " + \
                   "assert not any('general_tools' in p for p in sys.path); " + \
                   "s=unittest.defaultTestLoader.loadTestsFromNames([" + \
                   "'test_conversation.ContinuationTests.test_three_followups_during_tool_preserve_receipt_without_replay'," + \
                   "'test_conversation.ContinuationTests.test_provider_finishes_naturally_and_obsolete_proposal_is_not_executed'," + \
                   "'test_conversation_segments.SegmentTests','test_autonomy_boundaries','test_work_owner']); " + \
                   "r=unittest.TextTestRunner().run(s); sys.exit(not r.wasSuccessful())"
            result = subprocess.run([sys.executable, '-c', code], cwd=target,
                                    env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
