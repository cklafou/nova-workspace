# @nova: Regress actual-request provenance, frozen follow-up obligations, and no-tools audit/repair behavior without live providers.
import asyncio
import importlib.util
import types
import copy
import json
import unittest
from unittest.mock import patch
import test_witness_delivery as delivery
from test_witness_delivery import nova, witness, call, text_of
import test_conversation_segments as segments_fixture
from test_conversation_segments import speak
from nova_cortex.request_contract import CurrentRequest
from nova_runtime.conversation import ActiveTurn


class Incoming:
    def __init__(self, text):
        self.text = text
    def to_messages(self, name, system, **kwargs):
        return [{'role': 'system', 'content': system}, {'role': 'user', 'content': self.text}]


class ContractTests(unittest.TestCase):
    def test_only_current_incoming_messages_seed_contract(self):
        contract = CurrentRequest.from_messages([
            {'role': 'user', 'content': 'Old topic: use no tools.'},
            {'role': 'assistant', 'content': 'Old completed answer.'},
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Read the current fixture.'}]}])
        self.assertEqual(contract.entries, ['Read the current fixture.'])
        self.assertFalse(contract.tools_forbidden)
        contract.add('Use no external tools or files. Give only the requested words.')
        frozen = contract.snapshot()
        contract.add('You may use tools now for a specific verification.')
        self.assertTrue(frozen.tools_forbidden)
        self.assertFalse(contract.tools_forbidden)
        self.assertNotIn('tools now', frozen.render())

    def test_no_edits_and_quoted_prohibitions_do_not_ban_read_tools(self):
        for text in ["Review this with tools, but do not modify files.",
                     "Do not write files. Read the current fixture.",
                     'Explain the phrase "no tools" in the text.',
                     "What does 'use no external tools' mean?",
                     "Do not interpret no tools as a current restriction."]:
            with self.subTest(text=text):
                self.assertFalse(CurrentRequest([text]).tools_forbidden)
        for text in ["Use no external tools or files.", "Do not use tools.",
                     "Please no tools for this reply.", "Tools are not allowed.",
                     "Cole → you: No tools. Give the requested wording."]:
            with self.subTest(text=text):
                self.assertTrue(CurrentRequest([text]).tools_forbidden)

    def test_cancelled_old_request_does_not_seed_new_admission(self):
        messages = [{'role':'user','content':'Use no tools.'},
                    {'role':'user','content':'Read fixture.txt.'}]
        self.assertFalse(CurrentRequest.from_messages(messages).tools_forbidden)
        # Exact admitted batch can intentionally carry both requirements; context is not admission.
        self.assertTrue(CurrentRequest.from_entries([{'content':'Use no tools.'},
            {'content':'Say the supplied phrase.', 'author':'TestEngineer'}]).tools_forbidden)

    def test_correction_does_not_override_check_three(self):
        prompt = text_of(witness.build_witness('A true but irrelevant correction.', [],
            reads_remaining=0, request_context='Requested wording: silver then gold.',
            structured_output=True, evidence_snapshot={'humans':'','spoken':'','session_tools':''}))
        self.assertIn('omits an explicit unanswered follow-up fails check 3', prompt)
        self.assertIn('Requested wording: silver then gold.', prompt)
        self.assertNotIn('Do not output JSON', prompt)
        self.assertNotIn('what always PASSES', prompt)

    def test_json_verdict_reason_cannot_dispatch_quoted_tool(self):
        raw = json.dumps({'status':'CONCERN', 'reason':'No evidence for ' + call('read_file', path='secret')})
        self.assertEqual(witness.parse_witness_verdict(raw).status, 'CONCERN')
        self.assertIsNone(witness.find_audit_tool_call(raw)[0])
        for malformed in [raw + '\n' + call(), '{"status":"PASS","reason":"ok","status":"CONCERN"}',
                          'PASS but CONCERN: do not approve', 'PASSAGE']:
            self.assertEqual(witness.parse_witness_verdict(malformed).status, 'INCOMPLETE')
            self.assertIsNone(witness.find_audit_tool_call(malformed)[0])


class RequestDeliveryTests(unittest.IsolatedAsyncioTestCase):
    setUp = delivery.DeliveryTests.setUp
    fetch = delivery.DeliveryTests.fetch
    worker = delivery.DeliveryTests.worker
    execute = delivery.DeliveryTests.execute
    verify = delivery.DeliveryTests.verify
    run_turn = delivery.DeliveryTests.run_turn
    stages = delivery.DeliveryTests.stages
    collect_audit = delivery.DeliveryTests.collect_audit

    async def test_no_tools_request_uses_one_verdict_only_audit_without_dispatch(self):
        self.generations = ['Silver is ready; I will add the next requested word when it arrives.']
        self.verdicts = [call('read_file', path='unrelated.md')]
        with patch.object(nova, '_was_asked_to_act', side_effect=nova._integrity.was_asked_to_act):
            await self.run_turn(transcript=Incoming('Use no external tools or files. Say silver is ready.'))
        self.assertEqual(self.reads, [])
        self.assertEqual(self.tools, [])
        self.assertEqual(len(self.audit_calls), 1)
        self.assertNotIn('assertion_challenge', self.stages())
        self.assertIn('witness_incomplete', self.stages())
        schema = self.audit_calls[0][1]['response_format']['json_schema']['schema']
        self.assertNotIn('anyOf', schema)
        self.assertEqual(set(schema['properties']), {'status','reason'})

    async def test_witness_file_instruction_never_becomes_human_tool_request(self):
        self.generations = ['The connection has been verified completely.',
                            'Silver is ready; I cannot establish audio delivery from here.']
        self.verdicts = ['CONCERN: Unsupported connection verification. Read the audio log file.',
                         json.dumps({'status':'PASS','reason':'Requested wording present, unsupported claim removed.'})]
        with patch.object(nova, '_was_asked_to_act', side_effect=nova._integrity.was_asked_to_act):
            await self.run_turn(transcript=Incoming('Use no external tools or files. Say silver is ready.'))
        self.assertEqual(self.tools, [])
        self.assertEqual(self.reads, [])
        self.assertNotIn('assertion_challenge', self.stages())
        correction = self.main_calls[1][-1]['content']
        self.assertIn('Say silver is ready', correction)
        self.assertIn('external tools and file reads are forbidden', correction)
        self.assertNotIn('Emit the tool call NOW', correction)

    async def test_receipt_claim_repair_honors_tool_ban_and_keeps_requested_answer(self):
        self.generations = ['I checked the desktop and everything passed.',
                            'Silver is ready. I have no new desktop evidence.']
        self.verdicts = ['PASS']
        actual_claims = nova._integrity.claims_a_receipt
        with patch.object(nova, '_claims_a_receipt', side_effect=actual_claims):
            await self.run_turn(transcript=Incoming('Do not use tools. Say silver is ready.'))
        self.assertIn('assertion_challenge', self.stages())
        self.assertEqual(self.tools, [])
        repair = self.main_calls[1][-1]['content']
        self.assertIn('Say silver is ready', repair)
        self.assertIn('Do not call external tools or read files', repair)
        self.assertNotIn('GENERATED them', repair)

    async def test_proposed_external_tool_is_not_executed_when_forbidden(self):
        self.generations = [call('read_file', path='unrelated.md'), 'Silver is ready; no external check was performed.']
        self.verdicts = ['PASS']
        await self.run_turn(transcript=Incoming('Use no external tools or files. Say silver is ready.'))
        self.assertEqual(self.tools, [])
        self.assertIn('was NOT executed', self.main_calls[1][-1]['content'])


    async def test_background_heavy_cannot_read_when_current_request_forbids_it(self):
        self.config.update(witness_max_rounds=1, heavy_witness_enabled=True,
                           binding_cloud_escalation=False)
        draft = 'Silver is ready and this includes a disputed claim about connection verification.'
        self.generations, self.verdicts = [draft, draft], ['CONCERN: File receipt does not verify connection.'] * 2
        seen, tasks = [], []
        def judge(*args, **kwargs):
            seen.append(kwargs)
            return call('read_file', path='should-not-read')
        loader = types.SimpleNamespace(exec_module=lambda module: None)
        create = asyncio.create_task
        def tracked(coro):
            task = create(coro); tasks.append(task); return task
        with patch.object(witness, 'is_checkable_fact_concern', return_value=True), \
             patch.object(importlib.util, 'spec_from_file_location', return_value=types.SimpleNamespace(loader=loader)), \
             patch.object(importlib.util, 'module_from_spec', return_value=types.SimpleNamespace(heavy_witness=judge)), \
             patch.object(nova.asyncio, 'create_task', side_effect=tracked):
            await self.run_turn(transcript=Incoming('Use no external tools or files. Say silver is ready.'))
            await asyncio.gather(*tasks)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0]['allow_reads'])
        self.assertIn('Say silver is ready', seen[0]['request_context'])
        self.assertEqual(self.reads, [])
        event = next(event for event in self.events if event['stage']=='witness_heavy')
        self.assertEqual(event['sides'], 'no_ruling')

class RequestSegmentTests(unittest.IsolatedAsyncioTestCase):
    setUp = segments_fixture.SegmentTests.setUp
    fetch = segments_fixture.SegmentTests.fetch
    worker = segments_fixture.SegmentTests.worker
    execute = segments_fixture.SegmentTests.execute
    verify = segments_fixture.SegmentTests.verify
    run_body = segments_fixture.SegmentTests.run_body
    collect_audit = segments_fixture.SegmentTests.collect_audit

    async def test_followup_coverage_survives_private_correction_and_frozen_progress(self):
        self.generations = [speak('Silver is ready; this is a progress segment.'),
                            'All tests are clean and the audio connection was fully verified from this end.', 'Gold follows silver; the requested wording is complete.']
        self.verdicts = ['PASS', 'CONCERN: Unsupported claim that all tests are clean.', 'PASS']
        turn = ActiveTurn()
        segments, prompts = [], []
        original_fetch = self.fetch
        async def provider(messages, token, **kwargs):
            if kwargs.get('preserve_messages'):
                prompts.append(text_of(messages))
                if len(prompts) == 1:
                    turn.push([{'content': 'Use no external tools or files. Add gold after silver, then finish.'}])
            return await original_fetch(messages, token, **kwargs)
        async def segment(text, meta):
            segments.append((text, copy.deepcopy(meta)))
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            await self.run_body(turn, on_segment=segment)
        self.assertNotIn('Add gold after silver', prompts[0])
        self.assertIn('Add gold after silver', prompts[1])
        self.assertIn('Add gold after silver', prompts[2])
        self.assertIn('Add gold after silver', self.main_calls[2][-1]['content'])
        self.assertIn(segments[0][0], prompts[2])
        self.assertEqual([meta['input_revision'] for _,meta in segments], [0,1])
        self.assertEqual(self.reads, [])
        self.assertEqual(len(segments), 2)

    async def test_pending_ban_stops_new_audit_read_without_erasing_completed_segment(self):
        self.generations = ['The first completed progress segment describes only the supplied words.',
                            'The remaining response now follows the accepted no-tools instruction.']
        self.verdicts = [call('read_file', path='should-not-read'), 'PASS', 'PASS']
        turn, received = ActiveTurn(), []
        original_fetch = self.fetch
        calls = []
        async def provider(messages, token, **kwargs):
            if kwargs.get('preserve_messages'):
                calls.append((text_of(messages), kwargs))
                if len(calls)==1:
                    turn.push([{'content':'Do not use any tools. Finish using supplied context.'}])
            return await original_fetch(messages, token, **kwargs)
        async def collect(text, meta): received.append((text,meta))
        with patch.object(nova, '_fetch_llama_streaming', side_effect=provider):
            await self.run_body(turn, on_segment=collect)
        self.assertEqual(self.reads, [])
        self.assertEqual(len(received), 2)
        self.assertEqual([meta['input_revision'] for _,meta in received], [0,1])
        self.assertNotIn('Do not use any tools.', calls[1][0])
        self.assertIn('newer accepted instruction forbids external reads', calls[1][0])
        self.assertNotIn('anyOf', calls[1][1]['response_format']['json_schema']['schema'])
