# Last updated: 2026-10-06 03:19:20
# @nova: Tests Drive export, git hooks and collaborator roles in disposable repositories.
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('fixture_drive_copy', ROOT/'general_tools/nova_sync/drive_copy.py')
drive_copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(drive_copy)
GIT = shutil.which('git') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
SH = str(Path(GIT).parents[1]/'bin/sh.exe')

class UpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'PATH':str(Path(GIT).parent)+os.pathsep+os.environ['PATH']})
        self.env.start()
        self.git('init', '-q'); self.git('config','user.name','Nova test fixture'); self.git('config','user.email','fixture@example.invalid')
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()
    def git(self,*args):
        return subprocess.check_output([GIT,*args],cwd=self.repo).decode().strip()
    def put(self,rel,text):
        p=self.repo/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8');return p
    def commit(self):
        self.git('add','.');self.git('-c','core.hooksPath=disabled-hooks','commit','-qm','fixture')
    def test_export_update_delete_and_preserve_inbox_and_unmanaged_files(self):
        self.put('.gitignore','Nova_Drive/\n')
        self.put('workspace/README.md','first');self.put('workspace/a.py','a=1');self.put('workspace/a.png','binary fixture')
        self.commit();result=drive_copy.export(self.repo)
        self.assertTrue(result['complete']);self.assertEqual(result['changed'],2)
        self.assertFalse((self.repo/'Nova_Drive/read/a.png').exists())
        self.put('Nova_Drive/inbox/cole.md','retain');self.put('Nova_Drive/read/manual.md','retain')
        self.put('workspace/README.md','second');(self.repo/'workspace/a.py').unlink();self.commit()
        result=drive_copy.export(self.repo)
        self.assertEqual((self.repo/'Nova_Drive/read/README.md').read_text(),'second')
        self.assertEqual(result['removed'],1)
        for rel in ['inbox/cole.md','read/manual.md']: self.assertEqual((self.repo/'Nova_Drive'/rel).read_text(),'retain')
        self.assertEqual(drive_copy.export(self.repo)['changed'],0)
    def test_export_filters_dependencies_large_files_and_binaries(self):
        self.assertFalse(drive_copy.wanted('workspace/node_modules/a.js',20))
        self.assertFalse(drive_copy.wanted('workspace/a.md',drive_copy.MAX_BYTES+1))
        self.assertFalse(drive_copy.wanted('workspace/a.dll',20))
        self.assertTrue(drive_copy.wanted('workspace/a.md',20))
    def test_interrupted_export_resumes_from_manifest(self):
        self.put('workspace/README.md','first');self.commit()
        with patch.object(drive_copy.time,'monotonic',side_effect=[0,2]):
            self.assertFalse(drive_copy.export(self.repo,time_budget=1)['complete'])
        self.assertTrue(drive_copy.export(self.repo)['complete'])
        self.assertEqual((self.repo/'Nova_Drive/read/README.md').read_text(),'first')
    def test_precommit_does_not_stage_collaborator_drafts(self):
        self.put('workspace/general_tools/architecture_map/orient.py','pass\n')
        for name in ['README.md','ARCHITECTURE.md','OPERATIONS.md','INDEX.md','Architecture/inventory.json']:
            self.put('workspace/Orient/'+name,'generated')
        self.commit()
        self.put('workspace/Orient/AI Notes/draft.md','unfinished collaborator draft')
        self.put('workspace/Orient/README.md','regenerated')
        subprocess.run([SH,str(ROOT/'general_tools/architecture_map/hooks/pre-commit')],cwd=self.repo,check=True)
        staged=self.git('diff','--cached','--name-only').splitlines()
        self.assertIn('workspace/Orient/README.md',staged)
        self.assertNotIn('workspace/Orient/AI Notes/draft.md',staged)
    def test_prepush_checks_large_history_without_uploading(self):
        self.put('workspace/a.txt','x'*100);self.commit();head=self.git('rev-parse','HEAD')
        line=f'refs/heads/main {head} refs/heads/main '+('0'*40)+'\n'
        for limit,expected in [('50',1),('200',0)]:
            result=subprocess.run([SH,str(ROOT/'general_tools/nova_sync/hooks/pre-push')],cwd=self.repo,input=line,text=True,capture_output=True,env=dict(os.environ,NOVA_PUSH_LIMIT=limit))
            self.assertEqual(result.returncode,expected,result.stderr)
    def test_astra_roles_and_prompt_identity_use_isolated_state(self):
        sys.path.insert(0,str(ROOT/'nova_body'))
        spec=importlib.util.spec_from_file_location('fixture_principals',ROOT/'nova_body/nova_cortex/principals.py')
        principals=importlib.util.module_from_spec(spec);spec.loader.exec_module(principals)
        with patch.object(principals,'_STATE',self.repo/'users.json'):
            for name in ['Astra','GPT Astra','Codex (GPT Astra)','Claude','Cowork Claude']:
                self.assertEqual(principals.role_of(name),'trusted')
                self.assertTrue(all(principals.may(name,c) for c in principals.CAPABILITIES))
            for name in ['astral','Catastra','Visitor','', 'unknown']:
                self.assertEqual(principals.role_of(name),'untrusted')
                self.assertFalse(principals.may(name,'restart'))
            frame=principals.frame_for_prompt('GPT Astra')
            self.assertIn('GPT collaborator',frame);self.assertNotIn('is Claude',frame)
            self.put('users.json',json.dumps({'principals':{'Astra':{'role':'untrusted'}}}))
            self.assertFalse(principals.may('GPT Astra','restart'))

class WatcherResilienceTests(unittest.TestCase):
    def test_broken_orient_does_not_abort_autosave_startup(self):
        import types
        from general_tools.nova_chat.tests.test_controller_repair import functions
        orient=types.ModuleType('architecture_map.orient');orient.refresh=Mock(side_effect=ValueError('invalid review registry'))
        with patch.dict(sys.modules, {'architecture_map':types.ModuleType('architecture_map'),'architecture_map.orient':orient}):
            ns=functions(ROOT/'general_tools/nova_sync/watcher.py',{'build_file_index'},{'WORKSPACE_DIR':ROOT})
            result=ns['build_file_index']()
        self.assertIn('error',result);self.assertFalse(result['changed'])

if __name__ == '__main__': unittest.main()
