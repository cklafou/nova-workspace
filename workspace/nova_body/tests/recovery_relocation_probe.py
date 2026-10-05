# @nova: Exercise crash recovery in a disposable relocated body while denying the original workspace and network.
import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

mode, body_name, forbidden_json = sys.argv[1:]
body = Path(body_name).resolve()
os.environ['NOVA_BODY'] = str(body)
os.environ['NOVA_WORKSPACE'] = str(body.parent)
sys.path.insert(0, str(body))
forbidden = [os.path.normcase(os.path.abspath(value)) for value in json.loads(forbidden_json)]

def audit(event, arguments):
    if event == 'socket.connect':
        raise AssertionError('Relocation fixture must not call a network provider')
    if event in ('open','os.listdir','os.scandir','os.chdir') and arguments and isinstance(arguments[0], (str,bytes,os.PathLike)):
        target = os.path.normcase(os.path.abspath(os.fsdecode(arguments[0])))
        if any(target == root or target.startswith(root+os.sep) for root in forbidden):
            raise AssertionError('Original workspace access blocked: '+target)
loop = asyncio.new_event_loop()  # Windows asyncio first creates its internal socket pair.
sys.addaudithook(audit)
class NoFace:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'general_tools' or fullname.startswith('general_tools.') or fullname.startswith('nova_chat'):
            raise AssertionError('Detached face imported')
sys.meta_path.insert(0, NoFace())

from nova_runtime.runtime import NovaRuntime
from nova_runtime.conversation_context import ConversationContext
from nova_cortex import tasking, executive
from nova_paths import body_path

async def main():
    runtime = NovaRuntime(workspace=body.parent)
    runtime.populate_touch = lambda **kwargs: None
    runtime.clear_touch_active = lambda: None
    manifest = json.loads((body/'dependencies.json').read_text(encoding='utf-8'))
    assert manifest['model']['required'] and manifest['model']['bundled'] is False
    assert str(body_path('SELF')).startswith(str(body))
    if mode == 'crash':
        tid = tasking.create('SYNTHETIC_TASK retain original objective', notes='Finish remaining work without replay')
        executive.set_active(tid)
        owner = runtime.work_owner.try_claim('autonomy', focus=tid)
        first = {'role':'user','author':'TestEngineer','content':'SYNTHETIC_GOAL finish the fixture',
                 'request_id':'fixture-0','reply_to':'message-0','conversation_id':'deleted-face', 'register':'voice_fast'}
        owner.bind_inputs([first])
        owner.record_phase('execution', 'SYNTHETIC_PHASE completed inspection; task remains open')
        await owner.checkpoint({'type':'generation_started','turn_id':'original-turn'})
        meta = {'turn_id':'original-turn','segment_index':1,'input_revision':0,'final':False,'audit':{'status':'INCOMPLETE'}}
        await owner.checkpoint({'type':'segment_prepared',**meta,'text':'SYNTHETIC_PART already delivered'})
        runtime.transcript.append('Nova','SYNTHETIC_PART already delivered',response_metadata=meta)
        await owner.checkpoint({'type':'segment_delivered',**meta,'text':'SYNTHETIC_PART already delivered'})
        runtime.work_owner.receive_input({**first,'content':'SYNTHETIC_FOLLOWUP preserve the file','request_id':'fixture-1','reply_to':'message-1'})
        await owner.checkpoint({'type':'tool_started','tool':'write_file','operation_id':'uncertain-write',
            'args':{'path':'proof.txt','content':'ONLY ONCE'}})
        (body/'proof.txt').write_text('ONLY ONCE',encoding='utf-8')
        os._exit(23)  # Real process death: no context manager or finalizer can save completion.

    for old in forbidden:
        try:
            with open(Path(old)/'forbidden-probe','r'): pass
        except AssertionError:
            pass
        else:
            raise AssertionError('Filesystem denial hook was not enforced')
    assert runtime.work_owner.recovery_pending
    saved = runtime.work_owner.store.data['active']
    tid = saved['focus']
    assert tasking.get(tid)['status'] == 'open'
    original_id = saved['id']
    captured = []
    counter = 0
    async def provider(transcript,on_token,on_done,on_error,**kwargs):
        nonlocal counter
        counter += 1
        grounding = kwargs['workspace_context']
        for marker in ('SYNTHETIC_IDENTITY','SYNTHETIC_MEMORY','SYNTHETIC_GOAL','SYNTHETIC_PHASE','SYNTHETIC_PART'):
            assert marker in grounding, marker
        checkpoint = kwargs['on_checkpoint']
        turn = 'relocated-turn-'+str(counter)
        await checkpoint({'type':'generation_started','turn_id':turn,'autonomous':kwargs.get('autonomous',False)})
        if not kwargs.get('autonomous'):
            assert isinstance(transcript, ConversationContext)
            assert [m['author'] for m in transcript.messages if (m.get('input') or {}).get('role')=='user'] == ['TestEngineer','TestEngineer']
            rendered = str(transcript.to_messages('Nova','fixture system',workspace_context=grounding))
            assert 'TestEngineer' in rendered and 'SYNTHETIC_FOLLOWUP' in rendered
            assert kwargs['register'] == 'voice_fast'
            denied = await checkpoint({'type':'tool_started','tool':'write_file','operation_id':'no-replay',
                'args':{'path':'proof.txt','content':'ONLY ONCE'}})
            assert denied['allow'] is False
            # Inspect real disposable bytes, then cite that observation for reconciliation.
            await checkpoint({'type':'tool_started','tool':'read_file','operation_id':'verification-read','args':{'path':'proof.txt'}})
            observed = (body/'proof.txt').read_text(encoding='utf-8')
            assert observed == 'ONLY ONCE'
            await checkpoint({'type':'tool_completed','operation_id':'verification-read',
                'outcome':{'ok':True,'status':'completed','text':observed}})
            accepted = await checkpoint({'type':'reconcile_attempt','operation_id':'uncertain-write',
                'outcome':'verified_completed','evidence':'The exact intended fixture content exists.',
                'verification_operation_ids':['verification-read']})
            assert accepted['allow'] is True
            text = 'SYNTHETIC_REMAINING handled without repeating the earlier part.'
            meta = {'turn_id':turn,'segment_index':1,'input_revision':0,'final':True,'audit':{'status':'PASS'}}
            await checkpoint({'type':'segment_prepared',**meta,'text':text})
            await kwargs['on_segment'](text,meta)
            await checkpoint({'type':'segment_delivered',**meta,'text':text})
        else:
            text = 'PROGRESS: SYNTHETIC_RESUMED original task after human attention'
        await on_done(text)
        await checkpoint({'type':'generation_finished','turn_id':turn})
        captured.append(turn)
    runtime.model_client.register({'Nova':SimpleNamespace(stream_response=provider)})
    assert await runtime.recover_pending_inputs()
    assert runtime.work_owner.store.data['active']['id'] == original_id
    assert runtime.work_owner.store.data['active']['state'] == 'paused'
    assert runtime.work_owner.recovery_inputs() == []
    assert (body/'proof.txt').read_text(encoding='utf-8') == 'ONLY ONCE'
    # Run the actual runtime phase loop with only host perception/periodic chores disabled.
    with patch.object(executive,'ensure_standing_chores',return_value=[]), patch.object(executive,'pick_execution_target',return_value=tid):
        async with runtime.work_owner.lease('autonomy',focus=tid) as owner:
            await runtime._run_one_wake('relocated recovery fixture',True,False,
                runtime._recent_text_headless,runtime._generate_headless,lambda busy:None,None,
                owner=owner,attend_inputs=runtime._attend_inputs_headless)
    board = tasking.get(tid)
    assert 'SYNTHETIC_RESUMED' in str(board), board
    assert board['status'] == 'open'
    messages = runtime.transcript.messages
    assert sum(m.get('content') == 'SYNTHETIC_PART already delivered' for m in messages) == 1
    assert sum(m.get('content','').startswith('SYNTHETIC_REMAINING') for m in messages) == 1
    assert not runtime.work_owner.recovery_inputs()
    assert not runtime.work_owner.recovery_pending
    assert len(captured) == 2
    receipt = {'ok':True,'original_workspace_denied':True,'old_body_absent':True,
        'identity_memory_task_context':True,'work_id_preserved':True,'uncertain_action_not_replayed':True,
        'explicit_read_receipt_reconciliation':True,'headless_human_then_original_task':True,
        'segmented_output_not_duplicated':True,'task_status':board['status'],
        'model_dependency':manifest['model'],'provider':'injected fixture; no live model',
        'input_authors':['TestEngineer','TestEngineer']}
    print(json.dumps(receipt))
try:
    loop.run_until_complete(main())
finally:
    loop.close()
