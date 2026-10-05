# @nova: Verify durable input/work recovery, uncertain action barriers and actual model delivery checkpoints in disposable bodies.
import asyncio
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
from nova_runtime.work_owner import WorkCoordinator, current_work_owner
from nova_runtime.recovery import RecoveryStore, RecoveryWriteError


def entry(text='original goal', suffix='0'):
    return {'role':'user', 'content':text, 'request_id':'r'+suffix, 'reply_to':'m'+suffix,
            'conversation_id':'fixture', 'register':'voice_fast'}


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'nova_body/logs/runtime/active_work.json'

    async def interrupted(self, *, tool=True, complete=False, partial=False, kind='autonomy'):
        owner_id = None
        coordinator = WorkCoordinator(self.path)
        try:
            async with coordinator.lease(kind, focus='task-17') as owner:
                owner_id = owner.id
                owner.bind_inputs([entry()])
                owner.record_phase('execution', 'Verified the first file, remaining goal stays open.')
                await owner.checkpoint({'type':'generation_started','turn_id':'turn-a'})
                if partial:
                    await owner.checkpoint({'type':'segment_prepared', 'turn_id':'turn-a', 'segment_index':1,
                        'input_revision':0,'final':False,'text':'Already delivered part','audit':{'status':'INCOMPLETE'}})
                    await owner.checkpoint({'type':'segment_delivered', 'turn_id':'turn-a','segment_index':1,
                        'input_revision':0,'final':False,'text':'Already delivered part','audit':{'status':'INCOMPLETE'}})
                if tool:
                    await owner.checkpoint({'type':'tool_started','turn_id':'turn-a','tool':'write_file',
                        'args':{'path':'result.txt','content':'one'},'operation_id':'attempt-1'})
                    if complete:
                        await owner.checkpoint({'type':'tool_completed','turn_id':'turn-a','operation_id':'attempt-1',
                            'outcome':{'ok':True,'status':'completed','text':'written and checked'}})
                coordinator.receive_input(entry('follow-up stays ordered', '1'))
                raise RuntimeError('simulated abrupt interruption')
        except RuntimeError:
            pass
        return owner_id

    async def test_goal_inputs_phases_and_partial_output_survive(self):
        identity = await self.interrupted(partial=True)
        restored = WorkCoordinator(self.path)
        self.assertTrue(restored.recovery_pending)
        self.assertEqual([r['content'] for r in restored.recovery_inputs()], ['original goal','follow-up stays ordered'])
        async with restored.lease('autonomy') as owner:
            self.assertEqual(owner.id, identity)
            self.assertEqual(owner.focus, 'task-17')
            self.assertEqual(owner.goal, 'original goal')
            self.assertEqual(restored.store.data['active']['attempts']['attempt-1']['state'], 'uncertain')
            context = owner.prompt_context(12000)
            for text in ['original goal','Already delivered part','Verified the first file','uncertain']:
                self.assertIn(text, context)
        self.assertTrue(restored.recovery_pending)

    async def test_uncertain_effect_blocks_all_mutations_but_allows_read_and_deliberate_reconcile(self):
        await self.interrupted()
        restored = WorkCoordinator(self.path)
        async with restored.lease('autonomy') as owner:
            denied = await owner.checkpoint({'type':'tool_started','tool':'run_command',
                'args':{'command':'other mutation'},'operation_id':'attempt-2'})
            self.assertFalse(denied['allow'])
            permitted = await owner.checkpoint({'type':'tool_started','tool':'read_file',
                'args':{'path':'result.txt'},'operation_id':'read-1'})
            self.assertTrue(permitted['allow'])
            await owner.checkpoint({'type':'tool_completed','operation_id':'read-1',
                'outcome':{'ok':True,'status':'completed','text':'fixture proves file absent'}})
            restored.resolve_attempt('attempt-1','verified_not_applied','Independent fixture filesystem check: target absent')
            permitted = await owner.checkpoint({'type':'tool_started','tool':'write_file',
                'args':{'path':'result.txt','content':'one'},'operation_id':'attempt-3'})
            self.assertTrue(permitted['allow'])

    async def test_completed_identical_mutation_is_not_replayed_after_restart(self):
        await self.interrupted(complete=True)
        restored = WorkCoordinator(self.path)
        async with restored.lease('autonomy') as owner:
            result = await owner.checkpoint({'type':'tool_started','tool':'write_file',
                'args':{'path':'result.txt','content':'one'},'operation_id':'repeat'})
            self.assertFalse(result['allow'])
            self.assertNotIn('repeat', restored.store.data['active']['attempts'])

    async def test_explicit_stop_not_a_crash_and_only_bound_inputs_cancel(self):
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('conversation') as owner:
            owner.bind_inputs([entry()])
            coordinator.receive_input(entry('independent pending', '1'))
            owner.mark_stopped()
        restored = WorkCoordinator(self.path)
        self.assertFalse(restored.recovery_pending)
        self.assertEqual(restored.store.data['history'][-1]['state'], 'stopped')
        self.assertEqual([e['content'] for e in restored.recovery_inputs()], ['independent pending'])

    async def test_final_coverage_not_partial_and_resumed_generation_can_finish(self):
        await self.interrupted(tool=False, partial=True, kind='conversation')
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('conversation') as owner:
            owner.bind_inputs(coordinator.recovery_inputs())
            await owner.checkpoint({'type':'generation_started','turn_id':'turn-b'})
            await owner.checkpoint({'type':'segment_delivered','turn_id':'turn-b','segment_index':1,
                'input_revision':0,'final':True,'text':'remaining work done','audit':{'status':'PASS'}})
            await owner.checkpoint({'type':'generation_finished','turn_id':'turn-b'})
        self.assertEqual(coordinator.recovery_inputs(), [])
        self.assertFalse(coordinator.recovery_pending)
        self.assertEqual(coordinator.store.data['history'][-1]['generations']['turn-a']['state'], 'continued')

    async def test_conversation_attention_does_not_complete_recovered_autonomous_work(self):
        await self.interrupted(tool=False)
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('conversation') as owner:
            self.assertEqual(owner.kind, 'autonomy')
            owner.record_phase('attention','answered human only')
        self.assertEqual(coordinator.store.data['active']['state'], 'paused')
        self.assertTrue(coordinator.recovery_pending)

    async def test_input_media_register_and_idempotency_are_preserved(self):
        coordinator = WorkCoordinator(self.path)
        value = entry('look at attachment')
        value['images'] = [{'dataUrl':'data:image/png;base64,fixture'}]
        key = coordinator.receive_input(value)
        value['content'] = 'caller mutation'
        restored = WorkCoordinator(self.path)
        accepted = restored.recovery_inputs()[0]
        self.assertEqual(accepted['content'], 'look at attachment')
        self.assertEqual(accepted['register'], 'voice_fast')
        self.assertEqual(accepted['images'][0]['dataUrl'], 'data:image/png;base64,fixture')
        self.assertEqual(restored.receive_input(accepted), key)
        self.assertEqual(len(restored.recovery_inputs()), 1)

    async def test_disk_failure_before_start_preserves_last_durable_state(self):
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('conversation') as owner:
            before = self.path.read_bytes()
            with patch('nova_runtime.recovery.os.replace', side_effect=OSError('fixture full disk')):
                with self.assertRaises(RecoveryWriteError):
                    await owner.checkpoint({'type':'tool_started','tool':'write_file','args':{},'operation_id':'never'})
            self.assertEqual(self.path.read_bytes(), before)
            self.assertNotIn('never', coordinator.store.data['active']['attempts'])

    async def test_release_disk_failure_frees_ownership_and_stop_still_cancels(self):
        coordinator = WorkCoordinator(self.path)
        entered = asyncio.Event()
        async def run():
            async with coordinator.lease('conversation'):
                entered.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(run())
        await entered.wait()
        owner = coordinator.active
        with patch('nova_runtime.recovery.os.replace', side_effect=OSError('full disk')):
            self.assertTrue(owner.request_stop())
            with self.assertRaises(RecoveryWriteError):
                await task
        self.assertIsNone(coordinator.active)
        self.assertTrue(owner.finished.is_set())
        self.assertTrue(coordinator._available.is_set())
        self.assertTrue(owner.stop_persistence_error)
        self.assertTrue(coordinator.snapshot()['persistence_error'])

    async def test_saved_final_publication_closes_only_conversation_recovery(self):
        for kind in ('conversation','autonomy'):
            path = self.path.with_name(kind+'.json')
            coordinator = WorkCoordinator(path)
            try:
                async with coordinator.lease(kind) as owner:
                    owner.bind_inputs([entry()])
                    await owner.checkpoint({'type':'generation_started','turn_id':'published'})
                    await owner.checkpoint({'type':'segment_prepared','turn_id':'published','segment_index':1,
                        'input_revision':0,'text':'durably in transcript','final':True,'audit':{'status':'PASS'}})
                    raise RuntimeError('crash after publication before acknowledgement')
            except RuntimeError: pass
            restored = WorkCoordinator(path)
            self.assertFalse(restored.confirm_publication('published',1,'different text'))
            self.assertTrue(restored.confirm_publication('published',1,'durably in transcript'))
            self.assertEqual(restored.recovery_inputs(), [])
            self.assertEqual(restored.recovery_pending, kind == 'autonomy')

    async def test_model_reconciliation_requires_real_later_read_receipts(self):
        await self.interrupted()
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('autonomy') as owner:
            event = {'type':'reconcile_attempt','operation_id':'attempt-1','outcome':'verified_not_applied',
                     'evidence':'claimed absent','verification_operation_ids':['invented']}
            self.assertFalse((await owner.checkpoint(event))['allow'])
            await owner.checkpoint({'type':'tool_started','tool':'read_file','args':{'path':'result.txt'},'operation_id':'actual-read'})
            await owner.checkpoint({'type':'tool_completed','operation_id':'actual-read',
                'outcome':{'ok':True,'status':'completed','text':'target absent in disposable fixture'}})
            event['verification_operation_ids'] = ['actual-read']
            self.assertTrue((await owner.checkpoint(event))['allow'])
            self.assertFalse(coordinator.recovery_blocked)

    async def test_unrelated_conversation_cannot_discard_original_recovery_barrier(self):
        await self.interrupted(complete=True, kind='conversation')
        coordinator = WorkCoordinator(self.path)
        new_input = {**entry('new independent request','2'), 'conversation_id':'other'}
        async with coordinator.lease('conversation') as owner:
            owner.bind_inputs([new_input])
            await owner.checkpoint({'type':'generation_started','turn_id':'other-turn'})
            await owner.checkpoint({'type':'segment_delivered','turn_id':'other-turn','segment_index':1,
                'input_revision':0,'final':True,'text':'new reply','audit':{'status':'PASS'}})
            await owner.checkpoint({'type':'generation_finished','turn_id':'other-turn'})
        self.assertTrue(coordinator.recovery_pending)
        original_key = next(row['input_key'] for row in coordinator.recovery_inputs() if row['content']=='original goal')
        async with coordinator.lease('conversation') as owner:
            self.assertTrue(owner.recovered)
            owner.bind_inputs([original_key])
            result = await owner.checkpoint({'type':'tool_started','tool':'write_file',
                'args':{'path':'result.txt','content':'one'},'operation_id':'repeat-old'})
            self.assertFalse(result['allow'])

    async def test_invalid_checkpoint_fails_without_reset(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(RecoveryWriteError): WorkCoordinator(self.path)
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{broken')


# Real stream_response/ModelClient integration, isolated with established provider/tool fakes.
import test_conversation as fixture
from test_witness_delivery import nova, call, Transcript
from nova_runtime.conversation import ActiveTurn
from nova_runtime.model_client import ModelClient


class RecoveryBodyTests(unittest.IsolatedAsyncioTestCase):
    worker = fixture.ContinuationTests.worker
    execute = fixture.ContinuationTests.execute
    verify = fixture.ContinuationTests.verify
    fetch = fixture.ContinuationTests.fetch
    run_body = fixture.ContinuationTests.run_body
    collect_audit = fixture.ContinuationTests.collect_audit

    def setUp(self):
        fixture.ContinuationTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'body/logs/runtime/active_work.json'

    async def test_actual_body_dispatch_has_durable_start_before_call_and_final_receipts(self):
        self.generations = [call('write_file',path='fixture.txt',content='test'),
                            'The fixture operation returned a recorded result; this is the completed reply.']
        self.verdicts = ['PASS']
        coordinator = WorkCoordinator(self.path)
        real_execute = self.execute
        def execute(tool,args,**kwargs):
            disk = json.loads(self.path.read_text(encoding='utf-8'))
            self.assertEqual(disk['active']['attempts'][kwargs['operation_id']]['state'], 'started')
            return real_execute(tool,args,**kwargs)
        self.router.execute_tool = execute
        async with coordinator.lease('conversation') as owner:
            owner.bind_inputs([entry()])
            await self.run_body(ActiveTurn(turn_id='actual-turn'))
        saved = coordinator.store.data['history'][-1]
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(next(iter(saved['attempts'].values()))['state'], 'completed')
        self.assertEqual(saved['segments']['actual-turn:1']['state'], 'delivered')
        self.assertEqual(coordinator.recovery_inputs(), [])

    async def test_actual_body_disk_failure_does_not_execute_side_effect(self):
        self.generations = [call('write_file',path='fixture.txt',content='test')]
        coordinator = WorkCoordinator(self.path)
        async with coordinator.lease('conversation') as owner:
            original = owner.checkpoint
            async def checkpoint(event):
                if event['type'] == 'tool_started':
                    raise RecoveryWriteError('fixture disk failure')
                return await original(event)
            owner.checkpoint = checkpoint
            async def noop(*args): pass
            client = ModelClient(); client.register({'Nova':nova})
            await client.generate('Nova', Transcript(), on_token=noop,on_done=noop,
                on_error=lambda msg: self._error(msg))
        self.assertEqual(self.tools, [])
        self.assertTrue(self.errors)
        self.assertTrue(coordinator.recovery_pending)

    async def test_actual_reconcile_control_uses_read_receipt_then_allows_verified_retry(self):
        from nova_voice.tool_result import ToolResult
        coordinator = WorkCoordinator(self.path)
        try:
            async with coordinator.lease('conversation') as owner:
                owner.bind_inputs([entry()])
                await owner.checkpoint({'type':'tool_started','tool':'write_file','args':{'path':'result.txt'},'operation_id':'old'})
                raise RuntimeError('crash')
        except RuntimeError: pass
        restored = WorkCoordinator(self.path)
        self.generations = [call('read_file',path='result.txt'), call('write_file',path='result.txt'),
            'The inspected fixture allowed a deliberate retry; the completed result is retained.']
        self.results = [ToolResult('Verified fixture target absent',status='succeeded'),ToolResult('Fixture target written',status='succeeded')]
        self.verdicts = ['PASS']
        base_fetch = self.fetch
        reconciled = False
        async def provider(messages, on_token, **kwargs):
            nonlocal reconciled
            if self.tools and not reconciled and not kwargs.get('preserve_messages'):
                reconciled = True
                return call('reconcile_attempt',operation_id='old',outcome='verified_not_applied',
                    evidence='The later read established the fixture target is absent.',verification_operation_ids=[self.tools[0][2]])
            return await base_fetch(messages,on_token,**kwargs)
        with patch.object(nova,'_fetch_llama_streaming',side_effect=provider):
            async with restored.lease('conversation') as owner:
                owner.bind_inputs(restored.recovery_inputs())
                await self.run_body(ActiveTurn(turn_id='reconciled'))
        self.assertEqual([tool[0] for tool in self.tools], ['read_file','write_file'])
        self.assertFalse(restored.recovery_pending)
        saved=restored.store.data['history'][-1]
        self.assertEqual(saved['attempts']['old']['state'],'verified_not_applied')
        self.assertEqual(saved['attempts']['old']['reconciliation']['verification_operation_ids'],[self.tools[0][2]])

    async def _error(self, message): self.errors.append(message)

    async def test_actual_body_recovery_hold_blocks_uncertain_replay(self):
        coordinator = WorkCoordinator(self.path)
        try:
            async with coordinator.lease('conversation') as owner:
                owner.bind_inputs([entry()])
                await owner.checkpoint({'type':'tool_started','tool':'write_file',
                    'args':{'path':'fixture.txt','content':'test'},'operation_id':'old'})
                raise RuntimeError('crash')
        except RuntimeError: pass
        restored = WorkCoordinator(self.path)
        self.generations = [call('write_file',path='fixture.txt',content='test'),
            'The previous file change has an uncertain outcome. I retained the goal and will inspect it before retrying.']
        self.verdicts = ['PASS']
        async with restored.lease('conversation') as owner:
            owner.bind_inputs(restored.recovery_inputs())
            await self.run_body(ActiveTurn(turn_id='resumed-turn'))
        self.assertEqual(self.tools, [])
        self.assertIn('System Recovery Hold', str(self.main_calls[-1]))
        self.assertTrue(restored.recovery_blocked)


class RelocationAcceptanceTests(unittest.TestCase):
    def test_fresh_process_recovers_relocated_synthetic_body_with_old_tree_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            old_workspace = root/'old-workspace'
            original = old_workspace/'nova_body'
            original.mkdir(parents=True)
            for package in ('nova_runtime','nova_cortex','nova_voice','nova_senses'):
                for source in (BODY/package).rglob('*.py'):
                    if '__pycache__' in source.parts: continue
                    target = original/source.relative_to(BODY)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,target)
            shutil.copyfile(BODY/'nova_paths.py',original/'nova_paths.py')
            fixtures = {
                'SELF/core/00_fixture.md':'<!-- @nova: Synthetic identity used only in relocation tests. -->\nSYNTHETIC_IDENTITY',
                'memory/STATUS.md':'<!-- @nova: Synthetic remembered fact used only in relocation tests. -->\nSYNTHETIC_MEMORY',
                'dependencies.json':json.dumps({'@nova':'Declare synthetic relocation dependencies honestly',
                    'model':{'required':True,'bundled':False,'provider':'external llama.cpp-compatible endpoint'},
                    'test_transport':'injected receipt fixture; no live weights or inference'}),
            }
            for name,value in fixtures.items():
                target=original/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(value,encoding='utf-8')
            script=root/'probe.py'; shutil.copyfile(BODY/'tests/recovery_relocation_probe.py',script)
            forbidden_repo=str(BODY.parents[1])
            env=dict(os.environ, PYTHONPATH='', PYTHONDONTWRITEBYTECODE='1')
            crash=subprocess.run([sys.executable,'-B',str(script),'crash',str(original),json.dumps([forbidden_repo])],
                cwd=original,env=env,text=True,capture_output=True,timeout=30)
            self.assertEqual(crash.returncode,23,crash.stdout+crash.stderr)
            relocated=root/'new-machine'/'NovaPortable'
            relocated.parent.mkdir()
            self.assertTrue(original.resolve().is_relative_to(root) and relocated.resolve().is_relative_to(root))
            os.replace(original,relocated)
            old_workspace.rmdir()  # Checked disposable parent; no original body remains available.
            resumed=subprocess.run([sys.executable,'-B',str(script),'resume',str(relocated),
                json.dumps([forbidden_repo,str(old_workspace)])],cwd=relocated,env=env,text=True,capture_output=True,timeout=40)
            self.assertEqual(resumed.returncode,0,resumed.stdout+resumed.stderr)
            receipt=json.loads(resumed.stdout.splitlines()[-1])
            self.assertTrue(receipt['ok'])
            self.assertTrue(receipt['uncertain_action_not_replayed'])
            self.assertTrue(receipt['headless_human_then_original_task'])
            output=os.environ.get('NOVA_RECOVERY_RECEIPT')
            if output:
                import hashlib
                receipt={'@nova':'Disposable hard-crash and relocated-body acceptance receipt', **receipt,
                    'source_sha256':{name:hashlib.sha256((BODY/name).read_bytes()).hexdigest() for name in
                        ['nova_runtime/runtime.py','nova_runtime/work_owner.py','nova_runtime/recovery.py',
                         'nova_runtime/transcript_store.py','nova_runtime/model_client.py','nova_voice/nova.py']}}
                destination=Path(output); destination.parent.mkdir(parents=True,exist_ok=True)
                temporary=destination.with_name(destination.name+'.tmp')
                temporary.write_text(json.dumps(receipt,indent=2),encoding='utf-8'); os.replace(temporary,destination)


if __name__ == '__main__': unittest.main()
