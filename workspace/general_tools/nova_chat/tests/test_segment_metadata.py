# @nova: Verify real transcript segment metadata filtering and disk persistence using only a temporary log directory.
import ast
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

SOURCE=Path(__file__).resolve().parents[1]/'transcript.py'
class SegmentMetadata(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
        source=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Transcript')
        source.body=[node for node in source.body if isinstance(node,ast.FunctionDef) and node.name in {'__init__','add','_persist','flush_all'}]
        self.namespace=dict(LOG_DIR=Path(self.temp.name),datetime=datetime,json=json,threading=threading,uuid=uuid)
        exec(compile(ast.Module(body=[source],type_ignores=[]),str(SOURCE),'exec'),self.namespace)
        self.transcript=self.namespace['Transcript']('fixture')
    def test_metadata_persists_explicit_audit_without_unknown_transport_fields_or_mutable_aliases(self):
        metadata=dict(id='response',run_id='run',turn_id='run',segment_index=1,input_revision=2,delivery='delivered',
            request_ids=[None,'voice'],reply_to_ids=['typed','echo'],content='never duplicate content here',token='secret-not-stored',
            audit={'status':'INCOMPLETE','reason':'Not verified','source':'inline','turn_id':'run','input_revision':2,'secret':'exclude'})
        message=self.transcript.add('Nova','Delivered result.',response_metadata=metadata)
        metadata['request_ids'].append('changed');metadata['audit']['reason']='mutated'
        stored=json.loads(self.transcript.log_path.read_text(encoding='utf-8'))
        self.assertEqual(stored,message)
        self.assertEqual(stored['response_metadata']['audit']['status'],'INCOMPLETE')
        self.assertEqual(stored['response_metadata']['audit']['reason'],'Not verified')
        self.assertEqual(stored['response_metadata']['request_ids'],[None,'voice'])
        self.assertNotIn('secret',json.dumps(stored));self.assertNotIn('content',stored['response_metadata'])
    def test_legacy_messages_remain_compatible_and_invalid_metadata_never_invents_pass(self):
        old=self.transcript.add('Cole','Hello')
        self.assertNotIn('response_metadata',old)
        bad=self.transcript.add('Nova','Result',response_metadata={'delivery':{},'segment_index':True,'input_revision':-1,
            'request_ids':[{}],'reply_to_ids':['x'],'audit':{'status':[],'reason':object()},'unknown':'ignored'})
        self.assertEqual(bad['response_metadata'],{'audit':{'status':'NOT_RUN'}})
        self.assertEqual(len(self.transcript.log_path.read_text(encoding='utf-8').splitlines()),2)

if __name__=='__main__':unittest.main()
