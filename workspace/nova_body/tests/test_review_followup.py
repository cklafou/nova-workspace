# Last updated: 2026-10-05 21:27:11
# @nova: Reproduces lifecycle, outcome and durable-queue edge cases from the shared review.
import socket
import sys
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nova_runtime.llama_control import LlamaControl
from nova_runtime.koels_equip import KoELSEquip
from nova_runtime.work_queue import WorkQueue
from nova_voice import tool_router
from nova_cortex import integrity

class ReviewFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
    def test_restart_fails_when_old_socket_never_releases(self):
        with socket.socket() as held:
            held.bind(('127.0.0.1',0));held.listen()
            c=LlamaControl(self.root,port=held.getsockname()[1],health=lambda:False,runner=Mock())
            c._start=Mock(return_value={'ok':True,'started':True})
            with patch('time.monotonic',side_effect=[0,20]): result=c.restart()
            self.assertFalse(result['ok']);c._start.assert_not_called()
    def test_restart_waits_for_socket_then_starts_exactly_once(self):
        c=LlamaControl(self.root,health=lambda:False);c._kill_port=Mock()
        c._wait_stopped=Mock(return_value=True);c._start=Mock(return_value={'ok':True,'started':True})
        result=c.restart();self.assertTrue(result['ok']);c._wait_stopped.assert_called_once();c._start.assert_called_once()
    def test_koels_does_not_claim_failed_restart_equipped_adapter(self):
        k=KoELSEquip(self.root,Mock());k.loaded_names=Mock(return_value=set())
        k.self_restart_with_loadout=Mock(return_value={'ok':False,'error':'old socket still open'})
        self.assertFalse(k.equip('fixture',{'fixture':{'adapter':'fixture.gguf'}},allow_restart=True)['ok'])
    def test_duplicate_append_refusals_are_receipted_as_refused(self):
        for text in ['# Existing heading\n', 'A substantial paragraph that is already present in the document and must not be duplicated.']:
            p=self.root/'file.md';p.write_text(text)
            receipt=self.root/'receipts.jsonl'
            with patch.object(integrity,'RECEIPTS_PATH',receipt):
                result=tool_router.execute_tool('append_file',{'path':str(p),'content':text})
            self.assertEqual(result.status,'refused');self.assertFalse(result.ok);self.assertEqual(p.read_text(),text)
    def test_crashed_leases_eventually_fail_visibly(self):
        q=WorkQueue(path=self.root/'queue.sqlite3');q.put({'event':'fixture'})
        for _ in range(5):self.assertIsNotNone(q.claim(lease_seconds=-1))
        self.assertIsNone(q.claim(lease_seconds=-1))
        self.assertEqual(q.snapshot()['counts'].get('failed'),1);self.assertTrue(q.snapshot()['errors'])
    def test_completed_event_can_recur_without_losing_its_new_payload(self):
        q=WorkQueue(path=self.root/'queue.sqlite3');first=q.put({'version':1},key='recurring')
        job=q.claim();q.finish(job['id'])
        second=q.put({'version':2},key='recurring');self.assertNotEqual(first,second)
        self.assertEqual(q.claim()['payload'],{'version':2})
    def test_outstanding_work_still_deduplicates(self):
        q=WorkQueue(path=self.root/'queue.sqlite3');jid=q.put({'event':'fixture'},key='same')
        self.assertEqual(jid,q.put({'event':'fixture'},key='same'));q.claim()
        self.assertEqual(jid,q.put({'event':'fixture'},key='same'))

if __name__=='__main__':unittest.main()
