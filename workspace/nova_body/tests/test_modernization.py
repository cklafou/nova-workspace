# Last updated: 2026-10-03 11:00:25
"""Isolated runtime contracts; never load a model or write Nova's personal state.

Run: python -m unittest discover -s nova_body/tests -v
"""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_voice import tool_router
from nova_voice.tool_result import ToolResult, tool_event
from nova_cortex import integrity
from nova_runtime.operations import Operations, Operation, current_operation, run_process, run_in_worker
from nova_cortex import tasking, executive
from nova_runtime.work_queue import WorkQueue
from nova_lancedb.indexer import MemoryIndexer


class Outcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.receipts = self.root / 'receipts.jsonl'
        self.addCleanup(self.tmp.cleanup)
        for target, value in [('nova_voice.tool_router.WORKSPACE_ROOT', self.root),
                              ('nova_cortex.integrity.RECEIPTS_PATH', self.receipts)]:
            p = patch(target, value); p.start(); self.addCleanup(p.stop)

    def test_nonzero_exit_matches_receipt_and_widget(self):
        result = tool_router.execute_tool('run_command', {'command': "Write-Output 'partial'; exit 7"})
        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 7)
        self.assertIn('partial', result.stdout)
        receipt = json.loads(self.receipts.read_text())
        event = tool_event('run_command', {}, result, duration_ms=result.duration_ms)
        self.assertFalse(receipt['ok'])
        self.assertTrue(event['error'])
        self.assertEqual(receipt['outcome'], event['outcome'])

    def test_empty_success(self):
        result = tool_router.execute_tool('run_command', {'command': 'exit 0'})
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout, '')

    def test_successful_read_is_not_classified_by_content(self):
        p = self.root / 'error.txt'; p.write_text('ERROR: example, not a failed read')
        result = tool_router.execute_tool('read_file', {'path': str(p)})
        self.assertTrue(result.ok)
        self.assertFalse(tool_event('read_file', {}, result)['error'])

    def test_missing_file_and_refused_write(self):
        self.assertFalse(tool_router.execute_tool('read_file', {'path': str(self.root/'missing')}).ok)
        result = tool_router.execute_tool('write_file', {'path': str(self.root/'empty'), 'content': ''})
        self.assertEqual(result.status, 'refused')
        self.assertFalse((self.root/'empty').exists())

    def test_launch_failure(self):
        with patch.object(tool_router, 'run_process', side_effect=OSError('missing shell')):
            result = tool_router.execute_tool('run_command', {'command': 'exit 0'})
        self.assertFalse(result.ok)
        self.assertIn('missing shell', result)

    def test_legacy_untyped_result_is_not_proof_of_success(self):
        with patch.object(tool_router, '_execute_tool_inner', return_value='looks fine'):
            result = tool_router.execute_tool('old_tool', {})
        self.assertIsNone(result.ok)
        self.assertEqual(tool_event('old_tool', {}, result)['outcome']['status'], 'unknown')

    def test_timeout_preserves_output_and_prior_effect(self):
        p = self.root/'effect.txt'
        result = run_process([sys.executable, '-u', '-c',
            f"from pathlib import Path; import time; Path({str(p)!r}).write_text('done'); print('partial',flush=True); time.sleep(10)"], timeout=0.6)
        self.assertEqual(result['status'], 'timed_out')
        self.assertIn('partial', result['stdout'])
        self.assertEqual(p.read_text(), 'done')


class Cancellation(unittest.IsolatedAsyncioTestCase):
    async def test_stop_waits_for_running_command(self):
        registry = Operations()
        observed = {}
        def work():
            result = run_process([sys.executable, '-u', '-c', 'import time; print("ready",flush=True); time.sleep(30)'])
            observed.update(result)
        task = asyncio.create_task(registry.run(asyncio.to_thread(work)))
        for _ in range(100):
            if registry.snapshot() and registry.snapshot()[0]['process_ids']: break
            await asyncio.sleep(0.01)
        result = await registry.stop()
        self.assertTrue(result['stopped'], result)
        self.assertEqual(observed['status'], 'cancelled')
        self.assertFalse(registry.snapshot())
        await asyncio.gather(task, return_exceptions=True)

    async def test_stop_during_generation_wait(self):
        registry = Operations()
        task = asyncio.create_task(registry.run(asyncio.sleep(60)))
        await asyncio.sleep(0)
        self.assertTrue((await registry.stop())['stopped'])
        self.assertTrue(task.cancelled())

    async def test_uncooperative_worker_is_not_reported_stopped(self):
        import threading
        registry=Operations();started=threading.Event();release=threading.Event()
        def work():started.set();release.wait(3)
        task=asyncio.create_task(registry.run(run_in_worker(work)))
        while not started.is_set():await asyncio.sleep(0.01)
        try:
            result=await registry.stop(timeout=0.02)
            self.assertFalse(result['stopped'])
            self.assertTrue(result['remaining'][0]['workers'])
        finally:
            release.set();await asyncio.gather(task,return_exceptions=True)
            for _ in range(100):
                if not registry.snapshot():break
                await asyncio.sleep(0.01)
        self.assertFalse(registry.snapshot())


class SchedulingAndEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for name,path in [('nova_cortex.tasking._STORE',self.root/'tasks.json'),
                          ('nova_cortex.executive._STATE',self.root/'autonomy.json')]:
            p=patch(name,path);p.start();self.addCleanup(p.stop)

    def test_new_priority_task_gets_turn_after_checkpoint(self):
        old=tasking.create('old',priority=3)
        self.assertEqual(executive.pick_execution_target(),old)
        new=tasking.create('new request',priority=1,author='Test evaluator')
        self.assertEqual(executive.pick_execution_target(),old)
        self.assertIn('checkpoint',tasking.get(new)['scheduling']['reason'])
        state=executive._load_state();state['focus_lease_until']=0;executive._save_state(state)
        self.assertEqual(executive.pick_execution_target(),new)
        self.assertEqual(tasking.get(new)['author'],'Test evaluator')

    def test_done_without_evidence_waits_for_review(self):
        tid=tasking.create('a claim')
        self.assertFalse(tasking.complete(tid,'DONE, trust me'))
        self.assertEqual(tasking.get(tid)['status'],'waiting')
        self.assertEqual(tasking.get(tid)['verification']['state'],'needs_review')
        self.assertTrue(tasking.complete(tid,'Cole checked',manual=True))

    def test_equal_priority_work_gets_a_turn(self):
        first=tasking.create('first',priority=1)
        second=tasking.create('second',priority=1)
        self.assertEqual(executive.pick_execution_target(),first)
        state=executive._load_state();state['focus_lease_until']=0;executive._save_state(state)
        self.assertEqual(executive.pick_execution_target(),second)
        state=executive._load_state();state['focus_lease_until']=0;executive._save_state(state)
        self.assertEqual(executive.pick_execution_target(),first)

    def test_wrong_artifact_cannot_complete(self):
        artifact=self.root/'answer.txt';artifact.write_text('wrong')
        tid=tasking.create('answer',acceptance=[{'kind':'file','path':str(artifact),'contains':'correct'}])
        self.assertFalse(tasking.complete(tid,'done'))
        artifact.write_text('correct')
        self.assertTrue(tasking.complete(tid,'done'))
        self.assertEqual(tasking.get(tid)['verification']['state'],'passed')

    def test_failing_test_process_blocks_completion(self):
        tid=tasking.create('test exit',acceptance=[{'kind':'command','argv':[sys.executable,'-c','raise SystemExit(3)']}])
        self.assertFalse(tasking.complete(tid))
        self.assertEqual(tasking.get(tid)['verification']['checks'][0]['exit_code'],3)

    def test_corrupt_board_is_not_silently_replaced(self):
        tasking._STORE.write_text('{bad')
        with self.assertRaises(RuntimeError): tasking.create('new')
        self.assertEqual(tasking._STORE.read_text(),'{bad')

    def test_changed_criteria_cannot_finish_using_old_evidence(self):
        tid=tasking.create('changing check')
        def verification(_):
            tasking.set_acceptance(tid,[{'kind':'file','path':'new-requirement.txt'}])
            return {'ok':True,'state':'passed','checks':[]}
        with patch('nova_cortex.verification.verify',verification):
            self.assertFalse(tasking.complete(tid,'done'))
        self.assertEqual(tasking.get(tid)['status'],'waiting')
        self.assertIn('changed',tasking.get(tid)['verification']['reason'])

    def test_expected_nonzero_exit_is_a_valid_negative_test(self):
        tid=tasking.create('reject invalid input',acceptance=[{'kind':'command',
            'argv':[sys.executable,'-c','raise SystemExit(2)'],'expect_exit':2}])
        self.assertTrue(tasking.complete(tid))


class ComputerSession(unittest.TestCase):
    def test_guest_lifetime_is_reused_and_closed_by_eof(self):
        from nova_computer import session
        from types import SimpleNamespace
        backend=SimpleNamespace(name='wsl',distro='test-guest',_wsl='wsl')
        with patch.object(session,'_sessions',{}), patch.object(session.subprocess,'Popen') as start:
            process=start.return_value;process.poll.return_value=None;process.pid=123
            self.assertEqual(session.ensure(backend),session.ensure(backend))
            start.assert_called_once()
            session.close()
            process.stdin.close.assert_called_once()
            process.wait.assert_called_once()
        with patch.object(session.subprocess,'Popen') as start:
            self.assertIsNone(session.ensure(SimpleNamespace(name='local-posix')))
            start.assert_not_called()


class DurableWork(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'jobs.sqlite3'
        self.addCleanup(self.tmp.cleanup)

    def test_event_survives_restart_and_expired_lease(self):
        q=WorkQueue(path=self.path);jid=q.put({'kind':'changed'},key='same')
        self.assertEqual(q.put({'kind':'changed'},key='same'),jid)
        job=q.claim(lease_seconds=-1)
        restarted=WorkQueue(path=self.path);self.assertEqual(restarted.claim()['id'],jid)
        restarted.finish(jid)
        self.assertFalse(restarted.ready())

    def test_memory_false_return_is_retained_and_retried(self):
        class Store:
            last_error='disk unavailable'
            ok=False
            def add_text(self,**kw): return self.ok
        store=Store();indexer=MemoryIndexer(self.path,lambda:store)
        jid=indexer.add_message('remember this','Evaluator','test')
        indexer.process_one()
        self.assertEqual(indexer.status()['counts']['pending'],1)
        self.assertIn('disk unavailable',indexer.status()['errors'][0]['error'])
        with indexer.queue.connect() as db: db.execute('UPDATE jobs SET due=0 WHERE id=?',(jid,))
        store.ok=True
        restarted=MemoryIndexer(self.path,lambda:store);restarted.process_one()
        self.assertEqual(restarted.status()['counts']['done'],1)

    def test_retry_limit_leaves_visible_failed_work(self):
        q=WorkQueue(path=self.path);jid=q.put({'kind':'broken'})
        for _ in range(5):
            with q.connect() as db: db.execute('UPDATE jobs SET due=0 WHERE id=?',(jid,))
            self.assertIsNotNone(q.claim());q.finish(jid,error='still broken')
        self.assertEqual(q.snapshot()['counts']['failed'],1)
        self.assertFalse(q.ready());self.assertEqual(q.retry_failed(),1);self.assertTrue(q.ready())

    def test_failed_embedder_does_not_return_fake_vector(self):
        from nova_lancedb import embedder
        with patch.object(embedder,'_load_text_model',return_value=None):
            with self.assertRaises(RuntimeError):embedder.embed_text('remember me')

    def test_backfill_preserves_bad_row_and_recovers_later_rows(self):
        from nova_lancedb import backfill
        root=self.path.parent
        sessions=root/'logs'/'chat_sessions';sessions.mkdir(parents=True)
        source=sessions/'sample_chat.jsonl'
        original='broken row\n'+json.dumps({'author':'Evaluator','content':'recover me','timestamp':'2026-10-01T01:02:03'})+'\n'
        source.write_text(original,encoding='utf-8')
        with patch.object(backfill,'body_path',lambda *p:root.joinpath(*p)):
            result=backfill.enqueue_records(WorkQueue('memory',self.path))
        self.assertEqual(result['records_considered'],1)
        self.assertEqual(result['errors'][0]['line'],1)
        self.assertEqual(source.read_text(encoding='utf-8'),original)
        self.assertEqual(result['queue']['counts']['pending'],1)

    def test_cached_hash_does_not_acknowledge_an_evicted_record(self):
        from nova_lancedb.hippocampus import NovaMemoryStore
        from nova_lancedb.embedder import content_hash
        store=NovaMemoryStore.__new__(NovaMemoryStore)
        store._ready=True;store._known_hashes={content_hash('restored record')}
        store._text_tbl=MagicMock();store._text_tbl.count_rows.return_value=0
        store._text_tbl.search.return_value.limit.return_value.metric.return_value.to_list.return_value=[]
        with patch('nova_lancedb.embedder.embed_text',return_value=[1.0]):
            self.assertTrue(store.add_text('restored record',source='archive:chat'))
        store._text_tbl.add.assert_called_once()


class StagedChanges(unittest.TestCase):
    def setUp(self):
        from nova_cortex import task_workspace
        self.ws=task_workspace
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for name,value in [('nova_cortex.tasking._STORE',self.root/'tasks.json'),
                           ('nova_cortex.task_workspace.WORKSPACE_ROOT',self.root),
                           ('nova_cortex.task_workspace.workspace_path',lambda p:self.root/p),
                           ('nova_cortex.task_workspace.body_path',lambda *p:self.root.joinpath('body',*p))]:
            x=patch(name,value);x.start();self.addCleanup(x.stop)
        self.file=self.root/'code'/'answer.txt';self.file.parent.mkdir();self.file.write_text('before')
        self.tid=tasking.create('fix answer',acceptance=[{'kind':'file','path':'code/answer.txt','contains':'after'}])
        self.plan=self.ws.prepare(self.tid,['code'])
        self.copy=self.root/self.plan['directory']/'code'/'answer.txt'

    def test_failed_checks_leave_original_alone(self):
        with self.assertRaises(ValueError):self.ws.promote(self.tid)
        self.assertEqual(self.file.read_text(),'before')

    def test_verified_promotion_keeps_checkpoint(self):
        self.copy.write_text('after')
        result=self.ws.promote(self.tid)
        self.assertEqual(self.file.read_text(),'after')
        self.assertEqual((Path(result['checkpoint'])/'code'/'answer.txt').read_text(),'before')

    def test_concurrent_original_edit_blocks_promotion(self):
        self.copy.write_text('after');self.file.write_text('human edit')
        with self.assertRaises(ValueError):self.ws.promote(self.tid)
        self.assertEqual(self.file.read_text(),'human edit')


class WakeIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_queued_work_reaches_execution_before_reflection(self):
        from nova_runtime.runtime import NovaRuntime
        from nova_runtime.operations import current_phase
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);artifact=root/'answer';artifact.write_text('verified')
            with patch.object(tasking,'_STORE',root/'tasks.json'), patch.object(executive,'_STATE',root/'state.json'), \
                 patch.object(executive,'ensure_standing_chores',return_value=[]), \
                 patch.object(integrity,'reconcile_board',return_value=None), \
                 patch('nova_runtime.runtime.WorkQueue',side_effect=lambda:WorkQueue(path=root/'events.db')):
                tid=tasking.create('concrete work',acceptance=[{'kind':'file','path':str(artifact),'contains':'verified'}])
                runtime=NovaRuntime.__new__(NovaRuntime);runtime.workspace=root
                class Bus:
                    async def publish(self,event):pass
                runtime.bus=Bus();runtime.populate_touch=lambda **kw:None;runtime.clear_touch_active=lambda:None
                async def emit(*a,**kw):pass
                runtime.emit=emit
                phases=[]
                async def generate(prompt,speak):
                    phases.append(current_phase.get());return 'DONE: artifact checked'
                await runtime._run_one_wake('pending event',False,False,lambda:'',generate,lambda x:None,None)
                self.assertEqual(phases,['execution'])
                self.assertEqual(tasking.get(tid)['status'],'done')

    async def test_old_directive_is_not_a_current_instruction(self):
        from nova_senses import environment
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'intent.json';p.write_text(json.dumps({'text':'old question','speaker':'Cole','consumed':False,'ts':'2000-01-01T00:00:00'}))
            with patch.object(environment,'_COLE_INTENT',p):
                self.assertEqual(environment.cole_directive(),'')
                self.assertIn('old question',p.read_text())


if __name__ == '__main__':
    unittest.main()
