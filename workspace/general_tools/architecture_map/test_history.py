# Last updated: 2026-10-03 10:59:53
"""Real disposable Git histories exercise noise filtering, cache refresh and diffs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from atlas_history import build_history, classify, history_diff, document_refs


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=Path(self.temp.name)
        self.ws=self.repo/'workspace';self.ws.mkdir()
        self.file=self.ws/'nova_body/nova_sample/a.py';self.file.parent.mkdir(parents=True)
        self.catalog=self.repo/'atlas/timeline.json';self.catalog.parent.mkdir();self.catalog.write_text('{}',encoding='utf8')
        self.git('init','-q');self.git('config','core.autocrlf','false')

    def tearDown(self):self.temp.cleanup()

    def git(self,*args,day=1):
        env=os.environ.copy();env.update({'GIT_AUTHOR_NAME':'Atlas test','GIT_AUTHOR_EMAIL':'atlas@example.invalid',
            'GIT_COMMITTER_NAME':'Atlas test','GIT_COMMITTER_EMAIL':'atlas@example.invalid',
            'GIT_AUTHOR_DATE':f'2026-01-{day:02d}T12:00:00+09:00','GIT_COMMITTER_DATE':f'2026-01-{day:02d}T12:00:00+09:00'})
        result=subprocess.run(['git','-C',str(self.repo),*args],env=env,capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr);return result.stdout

    def commit(self,text,day):
        self.file.write_text(text,encoding='utf8');self.git('add','--','workspace');self.git('commit','-qm','auto-commit',day=day)

    def test_noise_and_real_code_changes_are_distinguished(self):
        self.commit('# Last updated: one\ndef run():\n return 1\n',1)
        self.commit('# Last updated: two\ndef run():\n return 1\n',2)
        self.commit('# Last updated: three\ndef run():\n return 2\n',3)
        history=build_history(self.ws,self.catalog)
        self.assertIsNone(history['error'])
        days={d['date']:d for d in history['daily']}
        self.assertEqual('housekeeping',days['2026-01-02']['files'][0]['kind'])
        self.assertEqual(0,days['2026-01-02']['meaningful_files'])
        self.assertEqual('code',days['2026-01-03']['files'][0]['kind'])
        diff=history_diff(self.ws,history,'2026-01-03','nova_body/nova_sample/a.py')
        self.assertIn('- return 1',diff['text']);self.assertIn('+ return 2',diff['text'])

    def test_cache_refreshes_on_new_commit_and_reports_uncommitted_source(self):
        self.commit('def run(): return 1\n',1)
        first=build_history(self.ws,self.catalog)
        self.file.write_text('def run(): return 2\n',encoding='utf8')
        working=build_history(self.ws,self.catalog)
        self.assertEqual(1,len(working['working']))
        self.assertEqual(first['head'],working['head'])
        self.git('add','--','workspace');self.git('commit','-qm','Change result',day=2)
        second=build_history(self.ws,self.catalog)
        self.assertNotEqual(first['head'],second['head'])
        self.assertEqual(2,second['coverage']['scoped_commits'])
        self.assertFalse(second['working'])

    def test_private_and_tool_files_are_not_in_history_surface(self):
        private=self.ws/'memory/COLE.md';private.parent.mkdir();private.write_text('private fixture',encoding='utf8')
        tool=self.ws/'general_tools/unmapped.py';tool.parent.mkdir();tool.write_text('SECRET="fixture"',encoding='utf8')
        self.commit('def run(): pass\n',1)
        history=build_history(self.ws,self.catalog)
        self.assertEqual(['nova_body/nova_sample/a.py'],[f['file'] for d in history['daily'] for f in d['files']])
        for file in ['memory/COLE.md','../outside.py','general_tools/unmapped.py']:
            with self.assertRaises(PermissionError):history_diff(self.ws,history,'2026-01-01',file)

    def test_deleted_files_and_declarations_are_visible(self):
        self.commit('def one(): pass\n',1)
        self.commit('def two(): pass\n',2)
        second=build_history(self.ws,self.catalog)['daily'][0]['files'][0]
        self.assertEqual(['two'],second['added_symbols']);self.assertEqual(['one'],second['removed_symbols'])
        self.file.unlink();self.git('add','-u');self.git('commit','-qm','Retire fixture',day=3)
        self.assertEqual('removed',build_history(self.ws,self.catalog)['daily'][0]['files'][0]['kind'])

    def test_timestamp_text_inside_python_string_is_not_housekeeping(self):
        result=classify('a.py','VALUE="""\n# Last updated: one\n"""\n','VALUE="""\n# Last updated: two\n"""\n')
        self.assertEqual('code',result['kind'])
        result=classify('a.py','VALUE="""x \n"""\n','VALUE="""x\n"""\n')
        self.assertEqual('code',result['kind'])

    def test_docstring_change_does_not_claim_behavior_unchanged(self):
        result=classify('a.py','def f():\n """one"""\n return 1\n','def f():\n """two"""\n return 1\n')
        self.assertEqual('notes',result['kind']);self.assertIn('can still affect',result['summary'])

    def test_script_text_is_not_dismissed_as_a_python_header(self):
        before="cat <<'EOF'\n# Last updated: one\nEOF\n"
        after="cat <<'EOF'\n# Last updated: two\nEOF\n"
        self.assertEqual('definition',classify('setup.sh',before,after)['kind'])

    def test_missing_and_damaged_development_notes_are_visible(self):
        doc=self.ws/'Orient/note.md';doc.parent.mkdir();doc.write_text('before\0\0surviving evidence',encoding='utf8')
        records=document_refs(self.ws,[{'id':'test','refs':[{'file':'Orient/note.md','contains':'surviving evidence'},
                                                         {'file':'Orient/missing.md','contains':'gone'}]}])
        self.assertEqual(2,len(records[0]['problems']))
        self.assertEqual('surviving evidence',records[0]['evidence'][0]['text'])

    def test_no_git_does_not_prevent_the_atlas_from_building(self):
        with tempfile.TemporaryDirectory() as separate:
            result=build_history(Path(separate),Path(separate)/'timeline.json')
            self.assertEqual('unavailable',result['head']);self.assertIsNotNone(result['error'])


if __name__=='__main__':unittest.main()
