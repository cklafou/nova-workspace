# Last updated: 2026-10-05 21:33:05
# @nova: Keep local Python environments out of Git, sync, backup, audits and automatic context using disposable fixtures.
import ast
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import traceback
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

WORKSPACE = Path(__file__).resolve().parents[3]
SYNC = WORKSPACE / 'general_tools/nova_sync'


def load_parts(path, names, constants=(), namespace=None):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    nodes += [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    ns = dict(namespace or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    return ns


class VirtualenvExclusions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.source = self.make('general_tools/voice_gateway/source.py')
        self.doc = self.make('general_tools/voice_gateway/README.md')
        self.near = self.make('general_tools/venv_tools/helper.py')
        self.dependencies = [self.make(f'general_tools/voice_gateway/{env}/{rel}')
            for env in ('.venv', 'venv')
            for rel in ('Lib/site-packages/dependency.py', 'Lib/site-packages/README.md', 'share/nova_voice/moonshine-base/config.json')]

    def make(self, relative, content='# disposable source\n'):
        path = self.workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def watcher(self):
        return load_parts(SYNC / 'watcher.py', {'_handle', '_audit_should_skip', '_is_frozen_file',
                          'update_timestamp_in_file', 'run_pup_cycle'},
            {'EXCLUDE_DIRS', 'EXCLUDE_SUBPATHS', 'AUDIT_EXCLUDE_PREFIXES', 'EXCLUDE_FROM_TIMESTAMPS',
             'WORKSPACE_ROOT_FILES', 'STAMP_COOLDOWN_S', 'GENERATED_ARTIFACTS'},
            {'WORKSPACE_DIR': self.workspace, 'Path': Path, 'os': os, 're': re, 'time': time,
             '_LAST_STAMP': {}, '_similarity': Mock(return_value=1.0),
             'run_push_cycle': Mock(), 'run_sync_and_backup': Mock(), 'print_session_urls': Mock()})

    def test_git_rules_ignore_nested_environments_but_keep_adjacent_source(self):
        for source, dest in [(WORKSPACE.parent / '.gitignore', self.root / '.gitignore'),
                             (WORKSPACE / '.gitignore', self.workspace / '.gitignore')]:
            dest.write_bytes(source.read_bytes())
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        paths = ['workspace/' + str(p.relative_to(self.workspace)).replace('\\', '/') for p in self.dependencies]
        paths += ['.venv/pyvenv.cfg', 'nested/venv/Lib/test.py']
        for rel in paths:
            result = subprocess.run(['git', 'check-ignore', '-q', '--', rel], cwd=self.root)
            self.assertEqual(result.returncode, 0, rel)
        for p in (self.source, self.near):
            result = subprocess.run(['git', 'check-ignore', '-q', '--', str(p.relative_to(self.root))], cwd=self.root)
            self.assertEqual(result.returncode, 1, p)

    def test_ai_ignore_entries_and_builtins_do_not_depend_on_config_location(self):
        for path in (WORKSPACE.parent / '.aignore', WORKSPACE / '.aignore'):
            rules = path.read_text(encoding='utf-8').splitlines()
            self.assertIn('.venv', rules); self.assertIn('venv', rules)
        ns = self.watcher()  # Does not execute the optional startup config parser.
        self.assertTrue({'.venv', 'venv'} <= ns['EXCLUDE_DIRS'])

    def test_watcher_events_and_audit_queue_skip_dependencies_without_stamping(self):
        ns = self.watcher()
        ns['update_timestamp_in_file'] = Mock()
        handler = types.SimpleNamespace(changed_files=set(), last_event_time=0)
        for path in self.dependencies:
            ns['_handle'](handler, str(path))
            self.assertTrue(ns['_audit_should_skip'](path.relative_to(self.workspace).as_posix()))
        self.assertFalse(handler.changed_files)
        ns['update_timestamp_in_file'].assert_not_called()
        ns['_handle'](handler, str(self.source))
        self.assertEqual(handler.changed_files, {str(self.source)})
        self.assertFalse(ns['_audit_should_skip'](self.source.relative_to(self.workspace).as_posix()))

    def test_direct_timestamp_and_pup_cannot_rewrite_dependency_source(self):
        ns = self.watcher()
        private = self.dependencies[0]
        before = private.read_bytes()
        ns['update_timestamp_in_file'](private)
        self.assertEqual(private.read_bytes(), before)
        staged = self.make(private.name, '# staged replacement\n')
        ns['run_pup_cycle']()
        ns['_similarity'].assert_not_called()
        self.assertEqual(private.read_bytes(), before)
        self.assertTrue(staged.exists())
        ns['run_push_cycle'].assert_not_called()

    def test_drive_scan_never_hashes_dependencies_and_index_prunes_them(self):
        checksum = Mock(return_value='fixture-checksum')
        ns = load_parts(SYNC / 'drive.py', {'_scan_local_files', '_gemini_index_paths'},
            {'EXCLUDE_DIRS', 'EXCLUDE_DIR_PREFIXES', 'EXCLUDE_SUBPATHS', 'INCLUDE_EXTENSIONS',
             'EXCLUDE_FILES', 'SECRET_SUFFIXES'},
            {'WORKSPACE_DIR': self.workspace, 'Path': Path, '_file_checksum': checksum})
        files = ns['_scan_local_files']()
        expected = {p.relative_to(self.workspace).as_posix() for p in (self.source, self.doc, self.near)}
        self.assertEqual(set(files), expected)
        self.assertEqual({call.args[0] for call in checksum.call_args_list}, {self.source, self.doc, self.near})
        indexed = set(ns['_gemini_index_paths']())
        self.assertFalse(indexed.intersection(self.dependencies))
        self.assertIn(self.source, indexed)

    def test_weekly_backup_zip_contains_source_but_no_environment(self):
        out = self.root / 'backups'
        ns = load_parts(SYNC / 'backup.py', {'weekly_backup'},
            {'EXCLUDE_DIRS', 'EXCLUDE_SUBPATHS', 'INCLUDE_EXTENSIONS', 'MAX_WEEKLY_BACKUPS'},
            {'WORKSPACE_DIR': self.workspace, 'WEEKLY_BACKUP_DIR': out, 'datetime': datetime,
             'zipfile': zipfile, 'traceback': traceback, '_prune_backups': Mock()})
        self.assertTrue(ns['weekly_backup'](force=True))
        with zipfile.ZipFile(next(out.glob('*.zip'))) as archive:
            self.assertEqual(set(archive.namelist()), {p.relative_to(self.workspace).as_posix()
                                                       for p in (self.source, self.doc, self.near)})

    def test_drive_copy_rejects_even_accidentally_committed_dependencies(self):
        ns = load_parts(SYNC / 'drive_copy.py', {'wanted'}, {'MAX_BYTES', 'TEXT_SUFFIXES', 'SKIP_PARTS'}, {'Path': Path})
        for private in self.dependencies:
            self.assertFalse(ns['wanted']('workspace/' + private.relative_to(self.workspace).as_posix(), 32))
        self.assertTrue(ns['wanted']('workspace/general_tools/venv_tools/helper.py', 32))

    def test_path_audit_does_not_read_or_patch_installed_packages(self):
        ns = load_parts(SYNC / 'dir_patch.py', {'load_known_files', 'run_audit'},
            {'SKIP_DIRS', 'SKIP_FILES', 'SKIP_MD_FILES'},
            {'WORKSPACE_DIR': self.workspace, 'TOOLS_DIR': self.workspace / 'general_tools',
             'FILE_INDEX': self.workspace / 'missing-index.md', 'Path': Path, 're': re,
             'build_module_map': lambda _: {}, 'build_path_map': lambda _: {},
             'find_stale_imports': Mock(return_value=[]), 'find_stale_path_refs': Mock(return_value=[]),
             'find_stale_imports_md': Mock(return_value=[]), 'apply_fixes': Mock()})
        known = ns['load_known_files']()
        self.assertNotIn('dependency.py', known)
        original_read = Path.read_text
        reads = []
        def record_read(path, *args, **kwargs):
            reads.append(path)
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', record_read):
            self.assertEqual(ns['run_audit'](interactive=False, auto=False, report_only=True), 0)
        self.assertFalse(set(reads).intersection(self.dependencies))
        self.assertEqual(set(reads), {self.source, self.doc, self.near})
        ns['apply_fixes'].assert_not_called()

    def test_code_health_audit_prunes_envs_before_descent_and_keeps_project_findings(self):
        broken = self.make('general_tools/project_error.py', 'def broken(:\n')
        launcher = self.make('general_tools/voice_gateway/launch.cmd', '@python source.py\n')
        shells = [self.make(f'general_tools/voice_gateway/{env}/Scripts/activate.bat',
                            '@python vendor_only.py\n') for env in ('.venv', 'venv')]
        self.make('general_tools/archive/old.py', 'def archived(:\n')
        ns = load_parts(WORKSPACE / 'general_tools/audit_scripts.py',
                        {'_audit_paths', 'collect_files', 'collect_shell_files',
                         '_entrypoint_scripts', 'check_syntax'},
                        {'EXCLUDE_DIRS', 'EXCLUDE_SUBPATHS', 'EXCLUDE_FILES'},
                        {'Path': Path, 'os': os, 'ast': ast, 're': re,
                         'WORKSPACE_DIR': self.workspace, 'TOP_LEVEL_PY': [],
                         'SCAN_ROOTS': [self.workspace / 'general_tools'],
                         '_rel': lambda path: path.relative_to(self.workspace).as_posix()})
        walked, read = [], []
        actual_walk, actual_read = os.walk, Path.read_text
        def guarded_walk(*args, **kwargs):
            for entry in actual_walk(*args, **kwargs):
                walked.append(Path(entry[0]))
                self.assertFalse(set(Path(entry[0]).parts) & {'.venv', 'venv'})
                yield entry
        def guarded_read(path, *args, **kwargs):
            read.append(path)
            self.assertFalse(set(path.parts) & {'.venv', 'venv'})
            return actual_read(path, *args, **kwargs)
        with patch.object(os, 'walk', guarded_walk), patch.object(Path, 'read_text', guarded_read):
            files = ns['collect_files']()
            self.assertEqual(set(files), {self.source, self.near, broken})
            self.assertEqual(ns['collect_shell_files'](), [launcher])
            self.assertEqual(ns['_entrypoint_scripts'](), {'source.py'})
            issues = [issue for path in files for issue in ns['check_syntax'](path)]
        self.assertTrue(walked)
        self.assertEqual([(i['code'], i['file']) for i in issues],
                         [('SYNTAX', 'general_tools/project_error.py')])
        self.assertFalse(set(read).intersection(self.dependencies + shells))

    def test_code_health_audit_rejects_an_explicit_environment_root(self):
        ns = load_parts(WORKSPACE / 'general_tools/audit_scripts.py', {'_audit_paths'},
                        {'EXCLUDE_DIRS', 'EXCLUDE_SUBPATHS'}, {'Path': Path, 'os': os})
        with patch.object(os, 'walk', side_effect=AssertionError('Must not enter dependency tree')):
            self.assertEqual(list(ns['_audit_paths'](self.dependencies[0].parent, {'.py'})), [])

    def test_automatic_context_skips_inventory_and_explicit_dependency_mentions(self):
        source = WORKSPACE / 'nova_body/nova_cortex/workspace_context.py'
        ns = load_parts(source, {'_context_paths', '_inject_file'},
            {'SKIP_DIRS', 'TEXT_EXTENSIONS', 'ONDEMAND_FILE_MAX'},
            {'WORKSPACE_DIR': self.workspace, 'Path': Path, 'os': os,
             'workspace_path': lambda relative: self.workspace / relative})
        indexed = set(ns['_context_paths']())
        self.assertFalse(indexed.intersection(self.dependencies))
        self.assertIn(self.source, indexed)
        for private in self.dependencies:
            obj = types.SimpleNamespace(_on_demand={}, _known_files={})
            ns['_inject_file'](obj, private.relative_to(self.workspace).as_posix())
            self.assertEqual(obj._on_demand, {})
        with patch.object(os, 'walk', side_effect=AssertionError('Must not enter dependency tree')):
            self.assertEqual(list(ns['_context_paths'](self.dependencies[0].parent)), [])

    def test_orient_prunes_both_environment_names(self):
        ns = load_parts(WORKSPACE / 'general_tools/architecture_map/orient.py', set(), {'SKIP'})
        self.assertTrue({'.venv', 'venv'} <= ns['SKIP'])


if __name__ == '__main__':
    unittest.main()
