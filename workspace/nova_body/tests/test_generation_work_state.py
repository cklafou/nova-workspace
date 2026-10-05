# @nova: Verify current body work snapshots at real generation boundaries without providers or personal state.
import asyncio
import copy
import json
import hashlib
import unittest
from unittest.mock import patch
import test_witness_delivery as fixture
from test_witness_delivery import nova, witness, call, text_of
from nova_voice.tool_result import ToolResult
from test_conversation_segments import speak
from nova_runtime.conversation import ActiveTurn, ANCHOR, provider_messages
from nova_cortex.context_budget import fit_messages
from nova_cortex.request_contract import CurrentRequest

MARKER = "[System] CURRENT WORK STEP"


def step(messages):
    records = [m for m in messages if str(m.get('content', '')).startswith(MARKER)]
    assert len(records) == 1, len(records)
    assert records[0] is messages[-1]
    return json.loads(records[0]['content'].split('\n')[1])


class Transcript:
    def __init__(self, initial, history=()):
        self.initial, self.history = initial, list(history)
    def to_messages(self, name, system, **kwargs):
        return [{'role': 'system', 'content': system}, *copy.deepcopy(self.history),
                {'role': 'user', 'content': self.initial}]


class WorkStateTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixture.DeliveryTests.setUp
    fetch = fixture.DeliveryTests.fetch
    worker = fixture.DeliveryTests.worker
    execute = fixture.DeliveryTests.execute
    verify = fixture.DeliveryTests.verify

    async def run_body(self, turn=None, *, initial='Inspect the supplied fixture.', history=(),
                       request_inputs=None, on_boundary=None, on_segment=None):
        async def noop(*args): pass
        async def done(text): self.done.append(text)
        async def error(text): self.errors.append(text)
        await nova.stream_response(Transcript(initial, history), noop, done, error,
            steering=turn, on_segment=on_segment or noop, on_boundary=on_boundary,
            request_inputs=request_inputs)
        await asyncio.sleep(0)
        self.assertEqual(self.errors, [])

    async def test_correction_then_followup_refreshes_exact_step_not_frozen_audit_or_history(self):
        initial = 'Use no external tools. Say silver, then provide a short wrap-up.'
        update = 'Add gold after silver, then finish the same work.'
        first = 'Silver is ready and the output has certainly reached its listener.'
        fixed = 'Silver, then gold. The requested words are ready.'
        self.generations, self.verdicts = [first, fixed], [
            'CONCERN: The claim about reaching a listener lacks evidence.', 'PASS']
        turn = ActiveTurn(turn_id='correction-work')
        fetch = self.fetch
        async def provider(messages, token, **kwargs):
            if kwargs.get('preserve_messages') and not self.audit_calls:
                turn.push([{'content': update}])
            return await fetch(messages, token, **kwargs)
        old_now = '[NOW — initial snapshot] [Last human words: initial input]'
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider), \
             patch.object(witness, 'now_card', return_value=old_now):
            await self.run_body(turn, initial=initial,
                request_inputs=[{'content': initial, 'author': 'TestEngineer'}])
        first_messages, second_messages = self.main_calls
        initial_step, current_step = step(first_messages), step(second_messages)
        self.assertEqual(initial_step['input_revision'], 0)
        self.assertEqual(current_step['input_revision'], 1)
        self.assertEqual(current_step['turn_id'], 'correction-work')
        self.assertEqual(current_step['applied_incoming_requests'],
                         ['TestEngineer → you: ' + initial, update])
        self.assertEqual(current_step['committed_output_segments'], [])
        self.assertEqual(first_messages[:-1], second_messages[:len(first_messages)-1])
        self.assertIn(old_now, text_of(second_messages))
        correction = next(m['content'] for m in second_messages if
                          str(m.get('content', '')).startswith('[Your witness'))
        self.assertNotIn(update, correction)  # preserved frozen revision-zero correction
        self.assertNotIn(update, text_of(self.audit_calls[0][0]))
        self.assertIn(update, text_of(self.audit_calls[1][0]))
        self.assertIn('Older NOW cards', second_messages[-1]['content'])
        self.assertNotIn('This candidate finishes', second_messages[-1]['content'])
        self.assertEqual(self.done, [fixed])

    async def test_tool_and_attention_boundaries_keep_receipts_and_committed_segments(self):
        first = 'The supplied task is organized; I will inspect its fixture next.'
        final = 'The fixture receipt and attended correction are retained in the completed work.'
        self.generations = [speak(first), call('read_file', path='fixture.txt'), final]
        self.verdicts = ['PASS', 'PASS']
        context = [{'role': 'user', 'content': 'Keep the original task; use the corrected label.'},
                   {'role': 'assistant', 'content': 'The separate input has been attended.'}]
        async def boundary(facts):
            return copy.deepcopy(context) if facts['stage'] == 'tool_complete' else []
        await self.run_body(ActiveTurn(turn_id='tool-work'), on_boundary=boundary)
        states = [step(messages) for messages in self.main_calls]
        self.assertEqual([s['committed_output_segments'] for s in states], [[], [first], [first]])
        self.assertEqual([s['completed_tool_count'] for s in states], [0, 0, 1])
        self.assertEqual(states[2]['input_revision'], 1)
        self.assertEqual(states[2]['latest_attended_context'], context)
        self.assertEqual(states[2]['last_completed_action']['tool'], 'read_file')
        self.assertEqual(states[2]['last_completed_action']['operation_id'], self.tools[0][2])
        self.assertIn('fixture receipt', states[2]['last_completed_action']['observation_preview'])
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(states[2]['applied_incoming_requests'], ['Inspect the supplied fixture.'])
        self.assertTrue(all(m[0] == self.main_calls[0][0] for m in self.main_calls))

    async def test_normal_tool_without_attention_callback_exposes_actual_failed_receipt(self):
        self.generations = [call('read_file', path='fixture.txt'),
                            'The fixture could not be read; its failure receipt is retained.']
        self.results = [ToolResult('fixture missing', status='failed', exit_code=7)]
        self.verdicts = ['PASS']
        await self.run_body(ActiveTurn(turn_id='ordinary-tool'))
        current = step(self.main_calls[1])
        self.assertEqual(current['completed_tool_count'], 1)
        self.assertEqual(current['last_completed_action']['status'], 'failed')
        self.assertFalse(current['last_completed_action']['ok'])
        self.assertEqual(current['last_completed_action']['exit_code'], 7)
        self.assertEqual(current['last_completed_action']['operation_id'], self.tools[0][2])
        self.assertEqual(current['latest_attended_context'], [])

    async def test_phase_attention_before_provider_is_current_without_reclassifying_input(self):
        self.generations = ['The original task and the attended phase facts remain in scope.']
        self.verdicts = ['PASS']
        context = [{'role':'user', 'content':'A separate conversation changed the task label.'},
                   {'role':'assistant', 'content':'That conversation already received its reply.'}]
        served = False
        async def boundary(facts):
            nonlocal served
            if facts['stage'] == 'before_provider' and not served:
                served = True
                return context
            return []
        await self.run_body(ActiveTurn(turn_id='phase-work'), on_boundary=boundary)
        current = step(self.main_calls[0])
        self.assertEqual(current['input_revision'], 1)
        self.assertEqual(current['latest_attended_context'], context)
        self.assertEqual(current['applied_incoming_requests'], ['Inspect the supplied fixture.'])
        self.assertEqual(current['committed_output_segments'], [])

    async def test_cancelled_historical_requests_are_context_not_current_work(self):
        self.generations = ['The current request is answered using its supplied context.']
        self.verdicts = ['PASS']
        old = 'Cancelled task: Use no tools and report the obsolete label.'
        current = 'Use the supplied current label instead.'
        await self.run_body(ActiveTurn(), initial=current,
            history=[{'role':'user','content':old}],
            request_inputs=[{'content':current,'author':'TestEngineer'}])
        messages = self.main_calls[0]
        self.assertIn(old, text_of(messages[:-1]))
        self.assertEqual(step(messages)['applied_incoming_requests'], ['TestEngineer → you: '+current])
        self.assertNotIn(old, messages[-1]['content'])

    async def test_repair_retains_actual_continue_choice_without_prejudging_next_draft(self):
        first = 'This progress segment asserts an unsupported success before the remaining work.'
        fixed = 'The progress segment is corrected and the remaining work will follow.'
        final = 'The remaining requested sentence is complete.'
        self.generations = [speak(first), fixed, final]
        self.verdicts = ['CONCERN: The first success claim lacks a receipt.', 'PASS', 'PASS']
        delivered = []
        async def segment(text, meta): delivered.append((text, copy.deepcopy(meta)))
        await self.run_body(ActiveTurn(turn_id='continue-repair'), on_segment=segment)
        self.assertEqual([text for text, _ in delivered], [fixed, final])
        self.assertEqual([meta['final'] for _, meta in delivered], [False, True])
        self.assertEqual(step(self.main_calls[1])['committed_output_segments'], [])
        self.assertEqual(step(self.main_calls[2])['committed_output_segments'], [fixed])
        self.assertTrue(all('This candidate finishes' not in messages[-1]['content']
                            for messages in self.main_calls))

    async def test_empty_retry_has_one_identical_snapshot_and_no_history_mutation(self):
        self.generations = ['', 'The retried response addresses the same unchanged work.']
        self.verdicts = ['PASS']
        await self.run_body(ActiveTurn(turn_id='empty-retry'))
        self.assertEqual(step(self.main_calls[0]), step(self.main_calls[1]))
        self.assertEqual(self.main_calls[0], self.main_calls[1])


class SnapshotTests(unittest.TestCase):
    def test_large_duplicate_inputs_and_outputs_do_not_exhaust_original_fixed_budget(self):
        original = 'Original complete input: ' + 'x'*88000
        delivered = ['y'*70000, 'z'*70000]
        original_message = {'role':'user', 'content':original, ANCHOR:True}
        record = {'role':'user', ANCHOR:True, 'content':CurrentRequest([original]).render_step(
            turn_id='large-work', input_revision=0, delivered=delivered)}
        messages = [{'role':'system','content':'Retain the actual objective.'}, original_message, record]
        fitted = fit_messages(messages, max_chars=174000)
        self.assertEqual(fitted, messages)
        with self.assertRaisesRegex(ValueError, 'none were silently discarded'):
            fit_messages(messages, max_chars=len(original)-1)
        state = step(fitted)
        reference = state['applied_incoming_requests'][0]
        self.assertEqual(reference['sha256'], hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(reference['chars'], len(original))
        self.assertEqual(reference['omitted_chars'], len(original)-len(reference['excerpt']))
        self.assertEqual([r['index'] for r in state['committed_output_segments']], [0,1])
        self.assertLess(len(record['content']), 5000)

    def test_many_large_records_preserve_order_latest_identity_and_explicit_omission_count(self):
        values = [f'Input {i}: ' + str(i)*2000 for i in range(20)]
        record = {'role':'user','content':CurrentRequest(values).render_step(
            turn_id='ordered-work',input_revision=19)}
        references = step([record])['applied_incoming_requests']
        self.assertEqual([r['index'] for r in references if 'index' in r], [0,1,2,3,16,17,18,19])
        gap = next(r for r in references if 'omitted_entries' in r)
        self.assertEqual(gap['omitted_entries'], 12)
        middle = json.dumps(values[4:-4],ensure_ascii=False,separators=(',',':'))
        self.assertEqual(gap['sha256'],hashlib.sha256(middle.encode()).hexdigest())
        self.assertTrue(references[-1]['excerpt'].startswith('Input 19:'))
        self.assertLess(len(record['content']), 6000)

    def test_current_step_survives_clipping_without_accumulation_or_internal_wire_keys(self):
        contract = CurrentRequest(['Original objective.', 'Later accepted amendment.'])
        record = {'role':'user', ANCHOR:True, 'content':contract.render_step(
            turn_id='budget-work', input_revision=3, delivered=['An already delivered segment.'])}
        fitted = fit_messages([{'role':'system','content':'S'*6000}, record], max_chars=2400, per_message=15)
        self.assertIn(record, fitted)
        wire = provider_messages(fitted)
        self.assertNotIn(ANCHOR, wire[-1])
        self.assertEqual(step(wire)['applied_incoming_requests'], contract.entries)
        self.assertNotIn('This candidate finishes', record['content'])


if __name__ == '__main__':
    unittest.main()
