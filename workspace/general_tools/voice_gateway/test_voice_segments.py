# @nova: Verify ordered audited voice segments, terminal deduplication and preserved interruptible audio using fake backends.
from __future__ import annotations
import asyncio
import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from body import MemoryBody
from config import GatewayConfig
from nova_link import parse_event
from speech import SpeechPlayer, Utterance
from turns import VoiceSession

class Player:
    def __init__(self): self.queued=[]; self.interruptions=[]; self.paused=False
    def active(self): return bool(self.queued)
    def say(self, unit): self.queued.append(unit)
    def pause(self): self.paused=True
    def resume(self): self.paused=False
    def interrupt(self, reason, *, preserve_queue=False):
        self.interruptions.append((reason,preserve_queue))
        if not preserve_queue:self.queued.clear()

def frame(kind, **fields):
    result=dict(type=kind, author='Nova', id='m1', run_id='run1', turn_id='run1',
                request_id='r1', reply_to='u1', request_ids=['r1'], reply_to_ids=['u1'], input_revision=0,
                delivery='delivered', content='First delivered part.', segment_index=1,
                audit={'status':'INCOMPLETE','reason':'Explicitly unapproved','source':'inline'})
    result.update(fields)
    if 'audit' not in fields:
        result['audit'].update(input_revision=result['input_revision'],turn_id=result['turn_id'])
    return result

class Segments(unittest.TestCase):
    def setUp(self):
        self.player=Player();self.body=MemoryBody();self.cfg=GatewayConfig()
        self.session=VoiceSession(self.cfg,self.player,self.body,log=lambda *_:None)
        self.session.sent('r1','original')
        self.feed(dict(type='user_message',id='u1',request_id='r1'))
        self.feed(frame('message_start'))
    def feed(self, data):
        event=parse_event(data)
        if event:self.session.handle(event)
    def test_delivers_before_terminal_then_continues_and_never_replays_aggregate(self):
        first=frame('message_segment');self.feed(first);self.feed(first)
        self.assertIn('r1',self.session.pending)
        self.assertEqual([u.text for u in self.player.queued],['First delivered part.'])
        self.assertEqual(self.player.queued[0].audit['status'],'INCOMPLETE')
        self.session.sent('r2','followup')
        self.assertEqual(len(self.player.queued),1)  # committed output was not discarded
        self.feed(dict(type='user_message',id='u2',request_id='r2'))
        fields=dict(request_ids=['r1','r2'],reply_to_ids=['u1','u2'],input_revision=1)
        self.feed(frame('message_context',**fields))
        second=frame('message_segment',segment_index=2,content='Second delivered part.',**fields)
        self.feed(second);self.feed(second)
        self.assertEqual([u.index for u in self.player.queued],[0,1])
        self.assertEqual([u.segment_index for u in self.player.queued],[1,2])
        self.assertEqual(self.player.queued[-1].request_id,'r2')
        end=frame('message_end',segment_count=2,content='First delivered part.\n\nSecond delivered part.',**fields)
        self.feed(end);self.feed(end);self.feed(second)
        self.assertEqual(len(self.player.queued),2)
        self.assertEqual(self.session.pending,{})
    def test_actual_server_segment_builder_is_compatible_without_final_replay(self):
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from nova_chat.response_events import ResponseEvents
        events=ResponseEvents(author='Nova',message_id='actual',run_id='actual-run',request_id='r1',reply_to='u1')
        self.feed(events.event('message_start'))
        audit={'status':'INCOMPLETE','reason':'Explicitly not approved','source':'inline',
               'input_revision':0,'turn_id':'actual-run'}
        self.feed(events.segment('A committed update.',{'segment_index':1,'input_revision':0,
                  'turn_id':'actual-run','audit':audit}))
        self.assertIn('r1',self.session.pending)
        self.feed(events.event('message_end',delivery='delivered',content=events.delivered_content))
        self.assertEqual([u.text for u in self.player.queued],['A committed update.'])
        self.assertEqual(self.session.pending,{})

    def test_frozen_prior_revision_segment_after_context_update_is_valid_but_unseen_revision_is_not(self):
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from nova_chat.response_events import ResponseEvents
        events=ResponseEvents(author='Nova',message_id='actual',run_id='actual-run',request_id='r1',reply_to='u1')
        self.feed(events.event('message_start'))
        self.session.sent('r2','late followup');self.feed(dict(type='user_message',id='u2',request_id='r2'))
        events.apply_inputs([{'request_id':'r2','reply_to':'u2'}],1)
        self.feed(events.event('message_context'))
        audit={'status':'INCOMPLETE','reason':'Frozen evidence','source':'inline','input_revision':0,'turn_id':'actual-run'}
        segment=events.segment('Completed original work.',{'segment_index':1,'input_revision':0,'turn_id':'actual-run','audit':audit})
        self.feed({**segment,'input_revision':2})
        self.assertEqual(self.player.queued,[])
        self.feed(segment)
        self.assertEqual([u.text for u in self.player.queued],['Completed original work.'])
        self.assertEqual(set(self.session.pending),{'r1','r2'})
        self.feed(events.event('message_end',delivery='delivered',content=events.delivered_content))
        self.assertEqual(self.session.pending,{})
        self.assertEqual(len(self.player.queued),1)

    def test_gap_waits_for_missing_segment_and_invalid_identity_does_not_consume_cursor(self):
        for bad in [dict(run_id='wrong'),dict(turn_id='wrong'),dict(reply_to_ids=['wrong']),
                    dict(input_revision=1),dict(audit={'status':'PASS','input_revision':1,'turn_id':'run1'}),dict(segment_index=True),dict(segment_index=0),dict(author='Other')]:
            self.feed(frame('message_segment',**bad))
        self.feed(frame('message_segment',segment_index=2))
        self.assertEqual(self.player.queued,[])
        self.feed(frame('message_segment'))
        self.feed(frame('message_segment',segment_index=2,content='Second.'))
        self.assertEqual(len(self.player.queued),2)
    def test_no_final_binding_shortcut_and_nullable_foreign_id_cannot_claim_voice(self):
        self.session._contexts.clear()
        self.feed(frame('message_segment'))
        self.assertEqual(self.player.queued,[])
        self.feed(frame('message_context',request_id=None,request_ids=[None],input_revision=1))
        self.feed(frame('message_segment',request_id=None,request_ids=[None],input_revision=1))
        self.assertEqual(self.player.queued,[])
    def test_old_bound_input_survives_timeout_until_terminal_for_frozen_segments(self):
        now=[1000.0];self.session.clock=lambda:now[0]
        self.session.pending['r1'].sent_at=now[0]
        self.session.sent('r2','followup')
        self.feed(dict(type='user_message',id='u2',request_id='r2'))
        self.feed(frame('message_context',request_ids=['r1','r2'],reply_to_ids=['u1','u2'],input_revision=1))
        now[0]+=301
        self.assertEqual(self.session.sweep(),[])
        self.assertEqual(set(self.session.pending),{'r1','r2'})
        self.feed(frame('message_segment'))  # old but exactly bound revision
        self.assertEqual(len(self.player.queued),1)
        self.feed(frame('message_end',segment_count=1,request_ids=['r1','r2'],reply_to_ids=['u1','u2'],input_revision=1))
        self.assertEqual(self.session.pending,{})

    def test_committed_segment_before_followup_application_remains_useful(self):
        self.session.sent('r2','more detail')
        self.feed(frame('message_segment'))
        self.assertEqual(len(self.player.queued),1)
        self.assertIn('r1',self.session.pending)
        self.session.barge_in()
        self.assertTrue(self.player.paused)
        self.assertEqual(len(self.player.queued),1)
        self.session.cancel()
        self.assertEqual(self.player.queued,[])
        self.feed(frame('message_segment',segment_index=2))
        self.assertEqual(self.player.queued,[])
    def test_audit_gate_output_mute_and_terminal_without_received_parts_never_invent_audio(self):
        self.cfg.audit_gate='pass_only'
        self.feed(frame('message_segment'))
        self.assertEqual(self.player.queued,[])
        self.assertFalse(self.body.of('message')[-1]['eligible'])
        self.session.output_muted=True
        self.feed(frame('message_segment',segment_index=2,audit={'status':'PASS'}))
        self.assertEqual(self.player.queued,[])
        self.feed(frame('message_end',segment_count=3,content='Aggregate must not replay.'))
        self.assertEqual(self.player.queued,[])
        self.assertEqual(self.session.pending,{})
    def test_non_deliveries_and_non_nova_frames_never_speak(self):
        for delivery in ['error','cancelled','empty','suppressed','unsolicited']:
            self.setUp();self.feed(frame('message_segment',delivery=delivery))
            self.assertEqual(self.player.queued,[])
        self.assertIsNone(parse_event(frame('message_segment',author='Cole')))

class PreservedQueue(unittest.IsolatedAsyncioTestCase):
    async def test_barge_in_cuts_current_but_pauses_and_preserves_waiting_units(self):
        body=MemoryBody();started=threading.Event();release=threading.Event();spoken=[]
        class Audio:
            name='fake'
            def speak(self,text,should_stop,on_playback):
                if text=='First':
                    started.set();release.wait(2)
                if should_stop():return {'outcome':'skipped'}
                on_playback();spoken.append(text)
            def stop(self):release.set()
        player=SpeechPlayer(Audio(),body,tail_s=0).start();self.addAsyncCleanup(player.close)
        player.say(Utterance('First'));player.say(Utterance('Second',index=1,segment_index=2))
        self.assertTrue(await asyncio.to_thread(started.wait,1))
        player.pause();player.interrupt('barge_in',preserve_queue=True)
        await asyncio.sleep(.02)
        self.assertEqual(spoken,[])
        self.assertTrue(player.active())
        player.resume();await asyncio.wait_for(player.drain(),1)
        self.assertEqual(spoken,['Second'])
    async def test_close_or_explicit_stop_invalidates_held_and_queued_units(self):
        for close in [False,True]:
            spoken=[]
            class Audio:
                name='fake'
                def speak(self,text,**_):spoken.append(text)
                def stop(self):pass
            player=SpeechPlayer(Audio(),MemoryBody(),tail_s=0).start()
            player.pause();player.say(Utterance('Held'));player.say(Utterance('Queued'))
            await asyncio.sleep(0)
            if close:await player.close()
            else:
                player.interrupt('stopped');await asyncio.wait_for(player.drain(),1);await player.close()
            player.resume();await asyncio.sleep(0)
            self.assertEqual(spoken,[])
            with self.assertRaises(RuntimeError):player.say(Utterance('Late'))

if __name__=='__main__':unittest.main()
