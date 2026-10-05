# @nova: Verify production voice-worker output waits for an already-started human turn without audio, models or network.
import asyncio
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import control_worker as worker
import nova_link, stt, tts
from config import GatewayConfig

class CaptureOutputTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events=[];self.spoken=[];self.release=threading.Event();self.entered=threading.Event()
        self.cfg=GatewayConfig(half_duplex_tail_ms=0)
        self.control=worker.Control();outer=self
        class Mic:
            name='fake'
            async def utterances(self):
                yield 'Original human request'
                await asyncio.Future()
            def close(self):pass
        self.mic=Mic()
        class Audio:
            name='fake'
            def speak(self,text,should_stop=None,on_playback=None):
                outer.spoken.append(text);outer.entered.set();on_playback()
                while not outer.release.wait(.005):
                    if should_stop():return {'outcome':'cut'}
                return {'outcome':'played'}
            def stop(self):pass
            def close(self):pass
        self.audio=Audio()
        class Link:
            def __init__(self,*args):self.frames=asyncio.Queue();outer.link=self
            async def __aenter__(self):return self
            async def __aexit__(self,*_):pass
            async def say(self,text,request_id):
                self.rid=request_id
                await self.frames.put({'type':'user_message','id':'human','request_id':request_id})
                await self.frames.put(self.frame('message_start'))
            def frame(self,kind,**fields):
                data={'type':kind,'author':'Nova','id':'reply','run_id':'run','turn_id':'run',
                    'request_id':self.rid,'reply_to':'human','request_ids':[self.rid],
                    'reply_to_ids':['human'],'input_revision':0,'segment_index':1,
                    'delivery':'delivered','content':'First useful sentence. Second useful sentence.',
                    'audit':{'status':'PASS','input_revision':0,'turn_id':'run'}}
                data.update(fields);return data
            async def stop(self,*args,**kwargs):return True
            async def events(self):
                while True:yield nova_link.parse_event(await self.frames.get())
        self.enterContext(patch.object(nova_link,'NovaLink',Link))
        self.enterContext(patch.object(stt,'make_stt',return_value=self.mic))
        self.enterContext(patch.object(stt,'local_asset_status',return_value={'label':'fixture'}))
        self.enterContext(patch.object(tts,'make_tts',return_value=self.audio))
        self.enterContext(patch.object(worker,'report',side_effect=lambda kind,**kw:self.events.append((kind,kw))))
        self.task=None

    async def until(self,predicate):
        for _ in range(400):
            if predicate():return
            await asyncio.sleep(.005)
        self.fail('Fixture condition did not complete')

    async def start(self):
        self.task=asyncio.create_task(worker.voice(self.cfg,self.control))
        await self.until(lambda: self.control.session and self.control.session._contexts)

    async def asyncTearDown(self):
        self.release.set()
        self.control.command({'command':'stop'})
        if self.task:
            await asyncio.wait_for(self.task,2)

    async def test_half_duplex_queued_reply_cannot_discard_an_in_progress_utterance(self):
        await self.start()
        self.mic.on_state('hearing')
        await self.link.frames.put(self.link.frame('message_segment'))
        await self.until(lambda:self.control.session.player.active())
        await asyncio.sleep(.03)
        self.assertEqual(self.spoken,[],'Nova started output over a human turn already in progress')
        for phase in ('finishing_turn','transcribing'):
            self.mic.on_state(phase)
            self.assertTrue(self.mic.gate(),'Held output closed the capture gate and would discard this turn')
        self.mic.on_state('listening')
        await self.until(self.entered.is_set)
        self.assertFalse(self.mic.gate(),'Actual half-duplex output must still gate new capture')
        self.release.set();await self.control.session.player.drain()
        self.assertTrue(self.mic.gate())
        self.assertEqual(self.spoken,['First useful sentence.','Second useful sentence.'])

    async def test_capture_reset_after_recognition_failure_releases_queued_output(self):
        await self.start();self.mic.on_state('hearing');self.mic.on_state('transcribing')
        await self.link.frames.put(self.link.frame('message_segment'))
        await self.until(lambda:self.control.session.player.active())
        await asyncio.sleep(.02);self.assertEqual(self.spoken,[])
        self.mic.on_diagnostic('Speech recognition failed; listening continues')
        self.mic.on_state('listening')
        await self.until(self.entered.is_set)
        self.assertEqual(self.spoken,['First useful sentence.'])

    async def test_mute_and_explicit_stop_still_override_a_held_capture(self):
        await self.start();self.mic.on_state('hearing')
        await self.link.frames.put(self.link.frame('message_segment'))
        await self.until(lambda:self.control.session.player.active())
        self.control.command({'command':'mute','microphone':True})
        self.assertFalse(self.mic.gate())
        self.control.command({'command':'stop'})
        self.mic.on_state('listening')
        await self.task
        self.assertEqual(self.spoken,[])

    async def test_full_duplex_barge_in_keeps_later_units_held_until_capture_finishes(self):
        self.cfg.duplex='full';await self.start()
        await self.link.frames.put(self.link.frame('message_segment'))
        await self.until(self.entered.is_set)
        self.mic.on_speech_start();self.mic.on_state('hearing')
        await self.until(lambda:self.control.session.player.current is None)
        self.assertTrue(self.mic.gate())
        await asyncio.sleep(.02);self.assertEqual(self.spoken,['First useful sentence.'])
        self.mic.on_state('finishing_turn');self.mic.on_state('transcribing')
        self.mic.on_state('listening');self.release.set()
        await self.control.session.player.drain()
        self.assertEqual(self.spoken,['First useful sentence.','Second useful sentence.'])

if __name__=='__main__':unittest.main()
