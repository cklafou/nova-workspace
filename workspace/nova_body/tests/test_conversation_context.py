# @nova: Verify body-owned and face-delegated conversation formatting preserve frozen clock, labels, images and provider payloads without services.
import ast
from copy import deepcopy
from datetime import datetime as RealDateTime
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
BODY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BODY))
from nova_runtime.conversation_context import ConversationContext, build_messages, now_block
FACE=BODY.parent/'general_tools/nova_chat/transcript.py'

def face_methods():
    tree=ast.parse(FACE.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Transcript')
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_now_block','to_messages'}]
    ns={};exec(compile(ast.Module(body=methods,type_ignores=[]),str(FACE),'exec'),ns);return ns

class SharedContext(unittest.TestCase):
    def setUp(self):self.face=face_methods()
    def test_exact_frozen_face_and_body_output_including_labels_and_images(self):
        authored=[{'author':'Cole','content':'[Cole is speaking to you]\nHello'},
                  {'author':'Nova','content':'[EXEC:whoami] [READ:x] [WRITE:y]data[/WRITE]'},
                  {'author':'Claude','content':'Look','images':[{'dataUrl':'data:image/png;base64,AA=='}]},
                  {'author':'Nova','content':'Still explicit.', 'response_metadata':{'audit':{'status':'INCOMPLETE'}}}]
        clock='[FROZEN CLOCK]\n\n'
        expected=[{'role':'system','content':'STABLE\n\n'+clock+'\n\n--- WORKSPACE CONTEXT ---\ncontext\n--- END CONTEXT ---'},
                  {'role':'user','content':'Cole → you: Hello'},
                  {'role':'assistant','content':'[Nova ran a command] [Nova read a file] [Nova wrote a file]'},
                  {'role':'user','content':[{'type':'text','text':'Look'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}]},
                  {'role':'assistant','content':'Still explicit.'}]
        face=SimpleNamespace(messages=deepcopy(authored),_now_block=lambda:clock)
        self.assertEqual(self.face['to_messages'](face,'Nova',' STABLE\n','context'),expected)
        self.assertEqual(build_messages(authored,'Nova',' STABLE\n','context',now_block=clock),expected)
    def test_face_clock_hook_remains_overridable_and_prefix_order_is_unchanged(self):
        face=SimpleNamespace(messages=[],_now_block=lambda:'clock-A')
        self.assertEqual(self.face['to_messages'](face,'Nova','stable')[0]['content'],'stable\n\nclock-A')
        face._now_block=lambda:'clock-B'
        self.assertEqual(self.face['to_messages'](face,'Nova')[0]['content'],'clock-B')
        self.assertEqual(build_messages([],'Nova',now_block='')[0],{'role':'system','content':''})
    def test_other_client_author_roles_and_image_format_keep_existing_semantics(self):
        messages=[{'author':'Nova','content':'[EXEC:x]'}, {'author':'Claude','content':'reply'},
                  {'author':'Cole','content':'[Cole is speaking to you]\nimage','images':[{'dataUrl':'fixture'}]}]
        result=build_messages(messages,'Claude',now_block='clock')
        self.assertEqual(result[1],{'role':'user','content':'Nova → you: [EXEC:x]'})
        self.assertEqual(result[2],{'role':'assistant','content':'reply'})
        self.assertEqual(result[3]['content'][0]['text'],'[Cole is speaking to you]\nimage')
    def test_snapshot_is_private_and_provider_receives_no_persistence_metadata(self):
        records=[{'author':'Cole','content':'original','images':[{'dataUrl':'fixture'}], 'response_metadata':{'run_id':'private'}}]
        context=ConversationContext(records,now_block=lambda:'clock')
        records[0]['content']='mutated';records[0]['images'][0]['dataUrl']='mutated'
        result=context.to_messages('Nova')
        self.assertEqual(result[1]['content'][0]['text'],'original')
        self.assertEqual(result[1]['content'][1]['image_url']['url'],'fixture')
        self.assertNotIn('response_metadata',str(result))
    def test_original_clock_and_gap_are_identical_through_face_wrapper(self):
        class Frozen(RealDateTime):
            @classmethod
            def now(cls,tz=None):return cls(2026,10,5,22,0,0)
        context=ConversationContext([{'author':'Cole','content':'hello','timestamp':'2026-10-05T21:58:00'}])
        clock=SimpleNamespace(stamp=lambda:'Monday fixture',time_of_day=lambda:'night')
        with patch.dict(sys.modules,{'nova_senses':SimpleNamespace(clock=clock)}), patch('datetime.datetime',Frozen):
            body_text=now_block(context)
            face_text=self.face['_now_block'](context)
        self.assertEqual(face_text,body_text)
        self.assertIn('The previous message in this room was 2 minutes ago (from Cole).',body_text)
        self.assertTrue(body_text.startswith('[RIGHT NOW: it is Monday fixture — night.'))

if __name__=='__main__':unittest.main()
