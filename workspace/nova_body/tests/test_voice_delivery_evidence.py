# @nova: Verify voice delivery-stage evidence reaches body drafts and frozen audits without inventing playback or overriding requested content.
import asyncio
import copy
import json
import unittest
from unittest.mock import patch
import test_witness_delivery as fixture
from test_witness_delivery import nova, witness, text_of, call
from nova_cortex.request_contract import CurrentRequest, voice_delivery_context
from nova_runtime.conversation import ActiveTurn


class Incoming:
    def to_messages(self, name, system, **kwargs):
        return [{'role':'system','content':system},
                {'role':'user','content':'Use no external tools. Say silver is ready, then finish.'}]


class VoiceEvidencePolicyTests(unittest.TestCase):
    def test_voice_style_is_not_an_audio_receipt_and_snapshots_keep_stage_scope(self):
        for register in ('voice','voice_fast'):
            context = voice_delivery_context(register)
            self.assertIn('does not establish a live microphone', context)
            self.assertIn('CURRENT CANDIDATE is still a draft', context)
            self.assertIn('reported device playback only', context)
            self.assertIn('explicit report supports attributed hearing', context)
            request = CurrentRequest(['Say a supplied phrase.'], delivery_context=context)
            frozen = request.snapshot()
            request.delivery_context = 'new state'
            self.assertIn(context, frozen.render(['an older delivered text segment']))
            self.assertNotIn('new state', frozen.render())
        self.assertEqual(voice_delivery_context('text'), '')

    def test_normal_final_and_heavy_audits_share_evidence_stages_and_ordinary_language_exceptions(self):
        evidence = {'humans':'','spoken':'','session_tools':''}
        request = CurrentRequest(['Say the supplied phrase.'], delivery_context=voice_delivery_context('voice')).render()
        prompts = [witness.build_witness('A fixture reply.', [], reads_remaining=reads,
                    structured_output=True, request_context=request, evidence_snapshot=evidence)
                   for reads in (3,0)]
        prompts.append(witness.build_heavy_witness('A fixture reply.', [], request_context=request,
                       allow_reads=False, evidence_snapshot=evidence))
        for messages in prompts:
            text = text_of(messages)
            self.assertIn('received transcript, authored draft, synthesized WAV', text)
            self.assertIn('device completion does not show a listener heard it', text)
            self.assertIn('old or unrelated hearing is not current confirmation', text)
            self.assertIn('idiomatic acknowledgment', text)
            self.assertIn('explicit quotation/script', text)
            self.assertIn('attribution', text)
            self.assertIn('Do not demand audio receipts for ordinary conversation', text)


class VoiceDeliveryStreamTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixture.DeliveryTests.setUp
    fetch = fixture.DeliveryTests.fetch
    worker = fixture.DeliveryTests.worker
    execute = fixture.DeliveryTests.execute
    verify = fixture.DeliveryTests.verify
    collect_audit = fixture.DeliveryTests.collect_audit

    async def run_voice(self, *, steering=None, on_segment=None, register='voice_fast'):
        async def token(_): pass
        async def done(value): self.done.append(value)
        async def error(value): self.errors.append(value)
        await nova.stream_response(Incoming(), token, done, error, register=register,
            steering=steering, on_segment=on_segment,
            request_inputs=[{'content':'Use no external tools. Say silver is ready, then finish.', 'author':'TestEngineer'}])
        await asyncio.sleep(0)
        self.assertEqual(self.errors, [])

    async def test_voice_contract_is_in_main_system_and_same_candidate_audit(self):
        self.generations = ['Silver is ready; this reply contains the requested wording.']
        self.verdicts = [json.dumps({'status':'PASS','reason':'Requested wording, no playback claim.'})]
        await self.run_voice()
        contract = voice_delivery_context('voice_fast')
        self.assertIn(contract, self.main_calls[0][0]['content'])
        self.assertIn(contract, text_of(self.audit_calls[0][0]))
        self.assertEqual(self.reads, [])
        self.assertEqual(self.tools, [])
        self.assertEqual(self.done, ['Silver is ready; this reply contains the requested wording.'])

    async def test_stage_concern_repairs_claim_without_losing_requested_content(self):
        # Scripted auditor response validates the handoff, not the model's semantic judgment.
        wrong = 'Silver is ready and the listener has heard this response perfectly.'
        fixed = 'Silver is ready; the requested short response is complete.'
        self.generations = [wrong, fixed]
        self.verdicts = [json.dumps({'status':'CONCERN', 'reason':'Check 1: draft says "listener has heard this response" before publication; no matching recipient report.'}),
                         json.dumps({'status':'PASS', 'reason':'Requested wording remains; no unsupported delivery claim.'})]
        await self.run_voice()
        self.assertEqual(self.done, [fixed])
        self.assertIn('Say silver is ready', self.main_calls[1][-1]['content'])
        self.assertIn(voice_delivery_context('voice_fast'), self.main_calls[1][-1]['content'])
        self.assertEqual(self.tools, [])
        self.assertEqual(self.reads, [])

    async def test_delivered_segment_and_followup_do_not_invent_audio_stage_evidence(self):
        first = 'Silver is ready; I will continue after this short progress segment.'
        final = 'Gold follows silver, and that completes the requested sequence of words.'
        self.generations = [call('speak', text=first, **{'continue':True}), final]
        self.verdicts = ['PASS','PASS']
        turn, segments = ActiveTurn(), []
        async def delivered(text, metadata):
            segments.append((text,copy.deepcopy(metadata)))
            if len(segments)==1:
                turn.push([{'content':'Add gold after silver, then finish.'}])
        await self.run_voice(steering=turn, on_segment=delivered)
        self.assertEqual([metadata['input_revision'] for _,metadata in segments], [0,1])
        next_prompt = text_of(self.main_calls[1])
        self.assertIn('delivered as TEXT to the output adapter', next_prompt)
        self.assertIn('not a synthesis, playback, or listener-hearing receipt', next_prompt)
        self.assertIn('Add gold after silver', text_of(self.audit_calls[1][0]))
        self.assertIn(voice_delivery_context('voice_fast'), text_of(self.audit_calls[1][0]))
        self.assertEqual(self.done, [first+'\n\n'+final])
        self.assertEqual(self.reads, [])

    async def test_text_register_does_not_gain_voice_adapter_capability_claim(self):
        self.generations = ['The requested phrase is supplied as text, with no external action claim.']
        self.verdicts = ['PASS']
        await self.run_voice(register='text')
        self.assertNotIn('VOICE DELIVERY EVIDENCE', self.main_calls[0][0]['content'])
        self.assertNotIn('VOICE DELIVERY EVIDENCE', text_of(self.audit_calls[0][0]))
