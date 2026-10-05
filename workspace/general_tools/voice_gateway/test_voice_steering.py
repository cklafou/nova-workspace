# @nova: Verify ordered voice follow-ups preserve body work and bind one combined reply without real audio or models.
from __future__ import annotations
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from body import MemoryBody
from config import GatewayConfig
from nova_link import parse_event
from turns import VoiceSession


class Player:
    def __init__(self): self.queued, self.interruptions = [], []
    def active(self): return False
    def interrupt(self, reason): self.interruptions.append(reason)
    def say(self, item): self.queued.append(item)


def frame(kind, *, requests=None, replies=None, revision=0, **extra):
    data = dict(type=kind, author='Nova', id='m1', run_id='run1', request_id='r1', reply_to='u1',
                request_ids=['r1'] if requests is None else requests,
                reply_to_ids=['u1'] if replies is None else replies, input_revision=revision)
    data.update(extra)
    if kind == 'message_end':
        data.setdefault('content', 'Both instructions are included.')
        data.setdefault('delivery', 'delivered')
        data.setdefault('audit', {'status': 'INCOMPLETE', 'reason': 'Not approved', 'source': 'inline'})
    return data


class Correlation(unittest.TestCase):
    def setUp(self):
        self.player, self.body = Player(), MemoryBody()
        self.session = VoiceSession(GatewayConfig(), self.player, self.body, log=lambda *_: None)

    def feed(self, data):
        event = parse_event(data)
        if event is not None: self.session.handle(event)

    def submit(self, rid, reply):
        self.session.sent(rid, 'input ' + rid)
        self.feed(dict(type='user_message', request_id=rid, id=reply))

    def combined(self):
        self.submit('r1', 'u1'); self.feed(frame('message_start'))
        self.submit('r2', 'u2')
        self.feed(frame('message_context', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1))

    def test_followup_after_start_binds_latest_input_and_speaks_once(self):
        self.combined()
        end = frame('message_end', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1)
        self.feed(end); self.feed(end)
        self.assertEqual(len(self.player.queued), 1)
        self.assertEqual(self.player.queued[0].request_id, 'r2')
        self.assertEqual(self.player.queued[0].run_id, 'run1')
        self.assertEqual(self.player.queued[0].audit['status'], 'INCOMPLETE')
        self.assertEqual(self.session.pending, {})
        self.assertEqual(self.body.of('message')[-1]['request_id'], 'r2')
        self.assertTrue(any(e.get('scope') == 'audio' and e['state'] == 'waiting' for e in self.body.of('turn')))

    def test_bad_context_cannot_bind_followup(self):
        cases = [dict(run_id='forged'), dict(replies=['wrong', 'u2']), dict(replies=['u1', 'wrong']),
                 dict(requests=['r2', 'r1']), dict(replies=['u1']), dict(revision=None),
                 dict(requests=['r1', 'r1']), dict(revision=-1)]
        for bad in cases:
            with self.subTest(bad=bad):
                self.setUp(); self.submit('r1', 'u1'); self.feed(frame('message_start')); self.submit('r2', 'u2')
                values=dict(requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1); values.update(bad)
                self.feed(frame('message_context', **values))
                self.feed(frame('message_end', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1))
                self.assertEqual(self.player.queued, [])
                self.assertIn('r2', self.session.pending)
                self.assertFalse(self.session.pending['r2'].message_ids)

    def test_initial_context_requires_an_acknowledged_local_pair_not_a_final_self_binding(self):
        self.submit('r1', 'u1'); self.submit('r2', 'u2')
        self.feed(frame('message_end', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1))
        self.assertEqual(self.player.queued, [])
        self.feed(frame('message_context', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1))
        self.assertEqual(self.session.pending['r2'].message_ids, {'m1'})
        self.feed(frame('message_start', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1))
        self.session.sent('r3', 'not yet acknowledged')
        self.feed(frame('message_context', requests=['r1', 'r2', 'r3'], replies=['u1', 'u2', 'u3'], revision=2))
        self.assertFalse(self.session.pending['r3'].message_ids)

    def test_bad_final_neither_speaks_nor_consumes_correct_pending_inputs(self):
        self.combined()
        good=frame('message_end', requests=['r1', 'r2'], replies=['u1', 'u2'], revision=1)
        cases=[{**good, 'run_id':'forged'}, {**good, 'reply_to_ids':['u1','wrong']},
               {**good, 'input_revision':0}, {**good, 'input_revision':True}, {**good, 'request_ids':['r1']},
               {key:value for key,value in good.items() if key not in ('request_ids','reply_to_ids')}]
        for bad in cases:
            self.feed(bad)
            self.assertEqual(self.player.queued, [])
            self.assertEqual(set(self.session.pending), {'r1', 'r2'})
        self.feed(good)
        self.assertEqual(len(self.player.queued), 1)

    def test_combined_terminal_outcomes_close_all_inputs_without_speech(self):
        for delivery in ['cancelled','error','empty','suppressed']:
            with self.subTest(delivery=delivery):
                self.setUp(); self.combined()
                self.feed(frame('message_end', requests=['r1','r2'], replies=['u1','u2'], revision=1, delivery=delivery))
                self.assertEqual(self.session.pending, {})
                self.assertEqual(self.player.queued, [])

    def test_old_final_does_not_answer_later_input_missing_from_its_revision(self):
        self.submit('r1','u1'); self.feed(frame('message_start')); self.submit('r2','u2')
        self.feed(frame('message_end'))
        self.assertEqual(self.player.queued, [])
        self.assertEqual(set(self.session.pending), {'r2'})

    def test_explicit_cancel_withholds_even_correct_combined_reply(self):
        self.combined(); self.session.cancel()
        self.feed(frame('message_end', requests=['r1','r2'], replies=['u1','u2'], revision=1))
        self.assertEqual(self.player.queued, [])
        self.assertEqual(self.session.pending, {})

    def test_context_author_filter_and_revision_cannot_roll_back(self):
        self.combined()
        self.assertIsNone(parse_event(frame('message_context', author='Other')))
        self.feed(frame('message_context'))
        self.feed(frame('message_end', requests=['r1','r2'], replies=['u1','u2'], revision=1))
        self.assertEqual(len(self.player.queued), 1)

    def test_typed_first_then_voice_can_join_even_when_original_start_was_missed(self):
        for saw_start in [True, False]:
            with self.subTest(saw_start=saw_start):
                self.setUp()
                initial = dict(request_id=None, reply_to='typed1', requests=[None], replies=['typed1'])
                if saw_start: self.feed(frame('message_start', **initial))
                self.submit('r2','u2')
                combined = dict(request_id=None, reply_to='typed1', requests=[None,'r2'], replies=['typed1','u2'], revision=1)
                self.feed(frame('message_context', **combined))
                self.feed(frame('message_end', **combined))
                self.assertEqual(len(self.player.queued),1)
                self.assertEqual(self.player.queued[0].request_id,'r2')
                self.assertEqual(self.session.pending,{})

    def test_voice_first_then_multiple_foreign_typed_inputs_preserve_owned_binding(self):
        self.submit('r1','u1'); self.feed(frame('message_start'))
        combined=dict(requests=['r1',None,None],replies=['u1','typed2','typed3'],revision=2)
        self.feed(frame('message_context',**combined))
        self.feed(frame('message_end',**combined))
        self.assertEqual(len(self.player.queued),1)
        self.assertEqual(self.player.queued[0].request_id,'r1')
        self.assertEqual(self.session.pending,{})

    def test_nullable_foreign_alias_cannot_claim_an_owned_input(self):
        self.submit('r1','u1')
        foreign=dict(request_id=None,reply_to='u1',requests=[None],replies=['u1'],revision=1)
        self.feed(frame('message_context',**foreign)); self.feed(frame('message_end',**foreign))
        self.assertEqual(self.player.queued,[])
        self.assertIn('r1',self.session.pending)

    def test_actual_server_builder_combined_context_matches_gateway(self):
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from nova_chat.response_events import ResponseEvents
        events=ResponseEvents(author='Nova',message_id='actual-m',run_id='actual-run',reply_to='typed1')
        self.feed(events.event('message_start'))
        self.submit('r2','u2')
        events.apply_inputs([{'request_id':'r2','reply_to':'u2'}],1)
        self.feed(events.event('message_context'))
        self.feed(events.event('message_end',content='Combined response.',delivery='delivered'))
        self.assertEqual(len(self.player.queued),1)
        self.assertEqual(self.player.queued[0].request_id,'r2')
        self.assertEqual(self.player.queued[0].message_id,'actual-m')
        self.assertEqual(self.session.pending,{})


class WorkerFollowups(unittest.IsolatedAsyncioTestCase):
    async def run_worker(self, *, end_before_reply):
        import control_worker as worker
        import nova_link, stt, tts
        records, events, queue = [], [], asyncio.Queue()
        first_started = asyncio.Event()
        control=worker.Control()
        class Link:
            def __init__(self,*args): self.ids=[]
            async def __aenter__(self): return self
            async def __aexit__(self,*args): records.append('closed')
            async def say(self,text,request_id):
                self.ids.append(request_id); records.append(('input',text,request_id))
                i=len(self.ids)
                await queue.put(parse_event(dict(type='user_message',request_id=request_id,id='u'+str(i))))
                data=dict(request_id=self.ids[0],reply_to='u1',requests=self.ids.copy(),
                          replies=['u'+str(j+1) for j in range(i)],revision=i-1)
                await queue.put(parse_event(frame('message_start' if i==1 else 'message_context',**data)))
                if i==2 and not end_before_reply:
                    await queue.put(parse_event(frame('message_end',**data)))
            async def stop(self,request_id,*,timeout_s):
                records.append(('stop',request_id))
                await queue.put(parse_event(dict(type='stopped',request_id=request_id,matched=True)))
                await asyncio.sleep(0)
                return True
            async def events(self):
                while True: yield await queue.get()
        class Mic:
            name='fake'
            gate=on_speech_start=on_state=on_diagnostic=None
            async def utterances(self):
                self.on_state('hearing'); self.on_state('finishing_turn'); self.on_state('transcribing')
                yield 'Original goal'
                await first_started.wait()
                self.on_speech_start()   # full-duplex audio interruption is local only
                self.on_state('hearing'); self.on_state('finishing_turn'); self.on_state('transcribing')
                yield 'Additional detail'
                await asyncio.Event().wait()
            def close(self): records.append('mic_closed')
        class Audio:
            name='fake'
            def speak(self,text,should_stop=None,on_playback=None):
                if should_stop(): return {'outcome':'skipped'}
                records.append(('spoken',text)); on_playback(); return {'outcome':'played'}
            def stop(self): records.append('audio_cut')
            def close(self): pass
        def report(kind,**fields):
            events.append(dict(type=kind,**fields)); e=fields.get('event',{})
            if e.get('type')=='turn' and e.get('phase')=='started':
                first_started.set()
                if e.get('input_revision')==1 and end_before_reply: control.command({'command':'stop'})
            if e.get('type')=='speech' and e.get('phase')=='end': control.command({'command':'stop'})
        cfg=GatewayConfig(duplex='full',barge_in=True,silence_ms=2000)
        with patch.object(nova_link,'NovaLink',Link), patch.object(stt,'make_stt',return_value=Mic()), \
             patch.object(stt,'local_asset_status',return_value={'label':'fake'}), \
             patch.object(tts,'make_tts',return_value=Audio()), patch.object(worker,'report',side_effect=report):
            await asyncio.wait_for(worker.voice(cfg,control),3)
        return records,events

    async def test_followup_and_barge_in_never_stop_work_combined_reply_speaks_once(self):
        records,events=await self.run_worker(end_before_reply=False)
        self.assertEqual([x[1] for x in records if isinstance(x,tuple) and x[0]=='input'],['Original goal','Additional detail'])
        self.assertFalse(any(isinstance(x,tuple) and x[0]=='stop' for x in records))
        self.assertEqual(len([x for x in records if isinstance(x,tuple) and x[0]=='spoken']),1)
        states={e['event'].get('state') for e in events if e['type']=='body'}
        self.assertTrue({'hearing','finishing_turn','transcribing'} <= states)
        self.assertTrue(any(e.get('settings',{}).get('end_of_turn_silence_ms')==2000 for e in events))

    async def test_end_call_stops_all_owned_pending_inputs_including_audio_retired_one(self):
        records,_=await self.run_worker(end_before_reply=True)
        inputs=[x[2] for x in records if isinstance(x,tuple) and x[0]=='input']
        stops=[x[1] for x in records if isinstance(x,tuple) and x[0]=='stop']
        self.assertEqual(stops,inputs)
        self.assertEqual(len(stops),2)
        self.assertTrue(all(records.index(('stop',rid)) < records.index('closed') for rid in stops))
        self.assertFalse(any(isinstance(x,tuple) and x[0]=='spoken' for x in records))


if __name__=='__main__': unittest.main()
