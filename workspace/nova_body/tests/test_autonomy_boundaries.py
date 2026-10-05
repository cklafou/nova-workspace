# @nova: Verify same-work attention at natural provider/tool boundaries without cancellation, receipt replay, or audit identity loss.
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
import test_witness_delivery as fixture
from test_witness_delivery import nova, witness, Transcript, call, text_of, operations, ToolResult
from nova_runtime.model_client import ModelClient
from nova_runtime.conversation import ANCHOR, RECEIPT_ANCHOR

_REAL_BEGIN_TURN = witness.begin_turn


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixture.DeliveryTests.setUp
    fetch = fixture.DeliveryTests.fetch
    worker = fixture.DeliveryTests.worker
    execute = fixture.DeliveryTests.execute
    verify = fixture.DeliveryTests.verify
    collect_audit = fixture.DeliveryTests.collect_audit

    async def run_body(self, callback, *, check_errors=True):
        async def noop(*args): pass
        async def done(text): self.done.append(text)
        async def error(text): self.errors.append(text)
        client = ModelClient()
        client.register({'Nova': nova})
        await client.generate('Nova', Transcript(), on_token=noop, on_done=done,
                              on_error=error, autonomous=True, on_boundary=callback,
                              on_audit=self.collect_audit)
        await asyncio.sleep(0)
        if check_errors:
            self.assertEqual(self.errors, [])

    async def test_provider_finishes_then_obsolete_proposal_is_reconsidered(self):
        started, release = asyncio.Event(), asyncio.Event()
        pending, observed, completed = [], [], []
        proposal = call('write_file', path='obsolete-target', content='do not write')
        final = 'The original goal remains active, and the attended update changes the next action.'
        self.generations = [proposal, final]
        self.verdicts = ['PASS']
        base_fetch = self.fetch
        async def provider(messages, token, **kwargs):
            if not self.main_calls and not kwargs.get('preserve_messages'):
                started.set()
                await release.wait()
                completed.append('natural completion')
            return await base_fetch(messages, token, **kwargs)
        async def boundary(facts):
            observed.append(copy.deepcopy(facts))
            if pending:
                self.assertEqual(completed, ['natural completion'])
                self.assertEqual(facts['stage'], 'provider_complete')
                pending.clear()
                return [{'role': 'user', 'content': 'FOLLOWUP ONE'},
                        {'role': 'assistant', 'content': 'ALREADY DELIVERED RESPONSE'},
                        {'role': 'user', 'content': 'FOLLOWUP TWO', 'private_owner': object()}]
            return []
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            task = asyncio.create_task(self.run_body(boundary))
            await asyncio.wait_for(started.wait(), 2)
            pending.append('human arrived during inference')
            await asyncio.sleep(0)
            self.assertEqual(len(observed), 1)
            self.assertFalse(task.done())
            release.set()
            await asyncio.wait_for(task, 3)
        self.assertEqual(self.tools, [])
        self.assertEqual(len(self.main_calls), 2)
        context = text_of(self.main_calls[1])
        for value in [proposal, 'NOT executed', 'FOLLOWUP ONE', 'FOLLOWUP TWO', 'ALREADY DELIVERED RESPONSE']:
            self.assertIn(value, context)
        self.assertTrue(self.main_calls[1][1][ANCHOR])
        followed = [m for m in self.main_calls[1] if m['content'] == 'FOLLOWUP TWO'][0]
        self.assertTrue(followed[ANCHOR])
        self.assertNotIn('private_owner', followed)
        self.assertEqual(self.delivery_audits[0]['input_revision'], 1)
        self.assertEqual({f['turn_id'] for f in observed}, {'fixture-run'})
        fact = next(f for f in observed if f['draft'] and f['draft']['tool_proposal'])
        self.assertFalse(fact['draft']['tool_proposal']['executed'])

    async def test_completed_tool_receipt_is_retained_once_before_attention(self):
        self.generations = [call('computer_exec', command='X' * 700),
                            'The completed tool attempt failed; its failure remains available after human attention.']
        self.results = [ToolResult('R' * 2000, status='failed', exit_code=127)]
        self.verdicts = ['PASS']
        observed, attended = [], []
        async def boundary(facts):
            observed.append(copy.deepcopy(facts))
            if facts['stage'] == 'tool_complete' and facts['phase'] == 'generation':
                self.assertEqual(len(self.tools), 1)
                attended.append(True)
                facts['last_completed_action']['status'] = 'malicious observer mutation'
                return [{'role': 'user', 'content': 'Continue original work; the human reply was delivered.'}]
            return []
        await self.run_body(boundary)
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(attended, [True])
        context = self.main_calls[1]
        self.assertIn('status=failed', text_of(context))
        self.assertIn('R' * 2000, text_of(context))
        self.assertTrue(any(m.get(RECEIPT_ANCHOR) for m in context))
        facts = next(f for f in observed if f['stage'] == 'tool_complete')
        action = facts['last_completed_action']
        self.assertEqual(action['operation_id'], self.tools[0][2])
        self.assertEqual((action['status'], action['ok'], action['exit_code']), ('failed', False, 127))
        self.assertLessEqual(len(action['args_preview']), 240)
        self.assertLessEqual(len(action['observation_preview']), 800)
        self.assertEqual(action['args_sha256'], hashlib.sha256(json.dumps(self.tools[0][1], sort_keys=True, ensure_ascii=False).encode()).hexdigest())
        later = next(f for f in observed if f['stage'] == 'before_delivery')
        self.assertEqual(later['last_completed_action']['status'], 'failed')

    async def test_human_input_waits_for_inflight_tool_receipt_then_continues_once(self):
        started, release = asyncio.Event(), asyncio.Event()
        pending, attended = [], []
        self.generations = [call('write_file', path='fixture', content='once'),
                            'The write completed once, and all three attended follow-ups remain in context.']
        self.verdicts = ['PASS']
        async def blocked_worker(fn, *args, **kwargs):
            started.set()
            await release.wait()
            return fn(*args, **kwargs)
        async def boundary(facts):
            if pending:
                self.assertEqual(facts['stage'], 'tool_complete')
                self.assertEqual(facts['completed_tool_count'], 1)
                self.assertEqual(len(self.tools), 1)
                batch = list(pending)
                pending.clear()
                attended.extend(batch)
                return [{'role': 'user', 'content': text} for text in batch]
            return []
        with patch.object(operations, 'run_in_worker', side_effect=blocked_worker):
            task = asyncio.create_task(self.run_body(boundary))
            await asyncio.wait_for(started.wait(), 2)
            pending.extend(['ATTENDED FIRST', 'ATTENDED SECOND', 'ATTENDED THIRD'])
            await asyncio.sleep(0)
            self.assertEqual(attended, [])
            self.assertFalse(task.done())
            release.set()
            await asyncio.wait_for(task, 3)
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(len(self.main_calls), 2)
        context = text_of(self.main_calls[1])
        for text in attended: self.assertIn(text, context)
        self.assertIn('fixture receipt', context)
        self.assertEqual(len(self.done), 1)

    async def test_explicit_stop_during_attention_prevents_next_provider_and_delivery(self):
        started = asyncio.Event()
        async def boundary(facts):
            started.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(self.run_body(boundary))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.main_calls, [])
        self.assertEqual(self.tools, [])
        self.assertEqual(self.done, [])

    async def test_before_delivery_attention_does_not_regenerate_completed_audited_phase(self):
        final = 'This completed autonomous phase has a supported result that should survive attention.'
        self.generations, self.verdicts = [final], ['PASS']
        attention = []
        async def boundary(facts):
            if facts['stage'] == 'before_delivery':
                attention.append(copy.deepcopy(facts))
                return [{'role': 'user', 'content': 'Human was answered; continue the same objective.'}]
            return []
        await self.run_body(boundary)
        self.assertEqual(self.done, [final])
        self.assertEqual(len(self.main_calls), 1)
        self.assertEqual(len(self.audit_calls), 1)
        self.assertEqual(attention[0]['audit']['status'], 'PASS')
        self.assertEqual(self.delivery_audits[0]['input_revision'], 0)

    async def test_audit_attention_keeps_frozen_sources_and_read_receipts(self):
        final = 'This phase result is assessed against the original evidence and completed audit reads.'
        self.generations = [final]
        self.verdicts = [call('read_file', path='fixture'), 'PASS']
        human = ['FROZEN HUMAN SOURCE']
        attended = []
        async def boundary(facts):
            if facts['phase'] == 'audit':
                attended.append(facts['stage'])
                human[0] = 'NEW HUMAN CONVERSATION'
                return [{'role': 'user', 'content': 'Already answered human update.'}]
            return []
        with patch.object(witness, 'human_record', side_effect=lambda: human[0]), \
             patch.object(witness, 'wire_record', side_effect=lambda: human[0]):
            await self.run_body(boundary)
        self.assertEqual(attended, ['provider_complete', 'tool_complete', 'provider_complete'])
        self.assertEqual(len(self.reads), 1)
        self.assertEqual(self.done, [final])
        self.assertEqual(len(self.main_calls), 1)
        for messages, _ in self.audit_calls:
            self.assertIn('FROZEN HUMAN SOURCE', text_of(messages))
            self.assertNotIn('NEW HUMAN CONVERSATION', text_of(messages))
        self.assertIn('fixture evidence remains inconclusive', text_of(self.audit_calls[1][0]))

    async def test_nested_turn_identity_restored_on_success_error_and_cancel(self):
        for outcome in ['success', 'error', 'cancel']:
            with self.subTest(outcome=outcome):
                self.done.clear(); self.errors.clear(); self.main_calls.clear()
                self.generations = ['The completed phase retains the outer pipeline identity.']
                self.verdicts = ['PASS']
                token = witness._CURRENT_TURN.set('OUTER')
                async def boundary(facts):
                    nested = _REAL_BEGIN_TURN()
                    self.assertNotEqual(nested, 'OUTER')
                    if outcome == 'error': raise ValueError('callback failed')
                    if outcome == 'cancel': raise asyncio.CancelledError()
                    return []
                try:
                    if outcome == 'cancel':
                        with self.assertRaises(asyncio.CancelledError):
                            await self.run_body(boundary)
                    else:
                        await self.run_body(boundary, check_errors=outcome == 'success')
                    self.assertEqual(witness._CURRENT_TURN.get(), 'OUTER')
                    if outcome != 'success': self.assertEqual(self.done, [])
                finally:
                    witness._CURRENT_TURN.reset(token)

    async def test_error_after_tool_stops_work_instead_of_replaying_it(self):
        self.generations = [call('write_file', path='fixture', content='once')]
        async def boundary(facts):
            if facts['stage'] == 'tool_complete':
                raise RuntimeError('private transport details')
            return []
        await self.run_body(boundary, check_errors=False)
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(len(self.main_calls), 1)
        self.assertEqual(self.done, [])
        self.assertEqual(self.errors, ['Nova client error: Work attention failed (RuntimeError)'])

    async def test_invalid_attention_context_prevents_unexecuted_side_effect(self):
        self.generations = [call('write_file', path='fixture', content='never')]
        async def boundary(facts):
            if facts['stage'] == 'provider_complete':
                return [{'role': 'system', 'content': 'invalid adapter contract'}]
            return []
        await self.run_body(boundary, check_errors=False)
        self.assertEqual(self.tools, [])
        self.assertEqual(self.done, [])
        self.assertIn('Work attention failed (ValueError)', self.errors[0])

    async def test_attention_does_not_replenish_total_step_budget(self):
        self.config['max_tool_loops'] = 1
        self.generations = [call('write_file', path='obsolete', content='never')]
        async def boundary(facts):
            if facts['stage'] == 'provider_complete':
                return [{'role': 'user', 'content': 'An update must not reset the budget.'}]
            return []
        await self.run_body(boundary)
        self.assertEqual(len(self.main_calls), 1)
        self.assertEqual(self.tools, [])
        self.assertEqual(len(self.done), 1)
        self.assertEqual(self.delivery_audits[0]['status'], 'NOT_RUN')

    async def test_legacy_client_receives_no_unused_optional_keyword(self):
        class Legacy:
            async def stream_response(_self, transcript, on_token, on_done, on_error, **kwargs):
                self.assertNotIn('on_boundary', kwargs)
                await on_done('legacy')
        client = ModelClient()
        client.register({'Nova': Legacy()})
        async def noop(*args): pass
        await client.generate('Nova', Transcript(), on_token=noop, on_done=noop, on_error=noop)


if __name__ == '__main__':
    unittest.main()
