# @nova: Guard audit evidence visibility, verdict precedence, image bounds and diagnostic redaction.
import sys
import json
from pathlib import Path
import unittest
from unittest.mock import patch

BODY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BODY))
from nova_cortex import witness
from nova_voice.tool_result import ToolResult, observation_text

class EvidenceTests(unittest.TestCase):
    def prompt(self, result, **kwargs):
        with patch.object(witness,'wire_record',return_value=''), patch.object(witness,'human_record',return_value=''), patch.object(witness,'session_tool_record',return_value=''):
            messages=witness.build_witness('Verify this claim.', [('computer_exec', {}, observation_text(result))], **kwargs)
        content=messages[1]['content']
        return content if isinstance(content,str) else '\n'.join(x.get('text','') for x in content)

    def test_environment_prose_cannot_crowd_out_stdout(self):
        r=ToolResult('watch?v=actual-video-id',environment={'target':'guest','shell':'bash','default_display':':1','note':'long note '*500},exit_code=0)
        p=self.prompt(r)
        self.assertIn('watch?v=actual-video-id',p)
        self.assertIn('exit=0 target=guest shell=bash default_display=:1',p)
        self.assertNotIn('long note',p)

    def test_window_and_unverified_postconditions_survive_receipts(self):
        text=json.dumps({'stdout':'','stderr':'','exit_code':0,'display':':1','verification':'application_window','page_verified':False,'playback_verified':False,'windows':[{'id':'123','title':'Example'}],'message':'Only a window was observed.'})
        p=self.prompt(ToolResult(text,status='unknown'))
        for word in ('page_verified','playback_verified','Only a window','123','status=unknown'):
            self.assertIn(word,p)

    def test_stderr_without_text_is_evidence(self):
        self.assertIn('cannot open display',self.prompt(ToolResult('',status='failed',exit_code=1,stderr='cannot open display')))

    def test_output_budget_discloses_omissions_and_retains_tail(self):
        text='BEGIN'+('x'*6000)+'ACTUAL END'
        p=self.prompt(ToolResult(text))
        self.assertIn('BEGIN',p)
        self.assertIn('ACTUAL END',p)
        self.assertIn('OUTPUT TRUNCATED',p)
        self.assertNotIn('x'*6000,p)

    def test_every_verdict_tag_takes_precedence_over_quoted_tool_json(self):
        for tag in ('PASS','CONCERN','REWRITE','INCOMPLETE','ERROR'):
            for wrapping in ('{s}', '2. {s}', '```text\n{s}\n```'):
                value=wrapping.format(s=tag+': evidence contains {"tool":"read_file","args":{"path":"x"}}')
                self.assertIsNone(witness.find_audit_tool_call(value)[0],value)
        self.assertEqual(witness.parse_witness_verdict('PASS: still malformed').status,'INCOMPLETE')

    def test_real_fenced_request_remains_a_request(self):
        call,_=witness.find_audit_tool_call('```json\n{"tool":"read_file","args":{"path":"x"}}\n```')
        self.assertEqual(call['tool'],'read_file')

    def test_user_and_tool_images_share_the_same_cap(self):
        frames=[{'label':str(i),'url':'data:image/png;base64,AA=='} for i in range(9)]
        chosen,omitted=witness.select_visual_evidence(frames,maximum=4)
        self.assertEqual([x['label'] for x in chosen],['5','6','7','8'])
        self.assertEqual(omitted,5)
        p=self.prompt(ToolResult(''),visual_evidence=frames,has_image=True)
        self.assertIn('5 earlier image(s) were omitted',p)

if __name__=='__main__':unittest.main()
