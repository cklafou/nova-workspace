# Last updated: 2026-10-03 10:57:52
"""Publishing checks using isolated files; no Nova model or personal state imported."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from orient import check, mark_reviewed, refresh


class OrientationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def test_updates_real_inputs_but_is_stable_without_changes(self):
        src = self.write('nova_body/nova_demo/a.py', 'VALUE = 1\n')
        self.assertTrue(refresh(self.root)['changed'])
        before = (self.root / 'Orient/INDEX.md').stat().st_mtime_ns
        self.assertFalse(refresh(self.root)['changed'])
        self.assertEqual(before, (self.root / 'Orient/INDEX.md').stat().st_mtime_ns)
        src.write_text('VALUE = 2\n')
        self.assertTrue(refresh(self.root)['changed'])
        self.write('nova_body/nova_demo/b.py', 'VALUE = 3\n')
        self.assertTrue(refresh(self.root)['changed'])
        self.assertIn('nova_demo/b.py', (self.root / 'Orient/INDEX.md').read_text())
        self.write('Orient/README.md', 'accidentally damaged')
        self.assertTrue(refresh(self.root)['changed'])
        self.assertIn('# Project Nova', (self.root / 'Orient/README.md').read_text())

    def test_sealed_and_secret_paths_are_never_read_or_indexed(self):
        self.write('models/do-not-touch.gguf', 'sealed fixture')
        self.write('nova_body/memory/.auth_token', 'secret fixture')
        self.write('nova_body/memory/COLE.md', 'private fixture')
        self.write('nova_body/logs/history.jsonl', 'private fixture')
        self.write('general_tools/example.py', 'pass\n')
        scan = os.scandir
        def guarded(path):
            if 'models' in Path(path).parts:
                raise AssertionError('entered sealed directory')
            return scan(path)
        with patch('os.scandir', guarded):
            refresh(self.root)
        index = (self.root / 'Orient/INDEX.md').read_text()
        for forbidden in ['do-not-touch', '.auth_token', 'COLE.md', 'history.jsonl']:
            self.assertNotIn(forbidden, index)
        self.write('nova_body/logs/new.jsonl', 'more runtime churn')
        self.write('Orient/Architecture/graph.json', '{}')
        self.assertFalse(refresh(self.root)['changed'])

    # ── Claude, 2026-10-02: the tests below pin down what makes Orient trustworthy, not just
    # regenerable. Paths that must NOT exist are built by concatenation so the live link check,
    # which scans the real workspace, never mistakes a fixture for a dangling pointer.

    def read(self, name):
        return (self.root / 'Orient' / name).read_text(encoding='utf-8')

    def test_review_flag_tracks_the_described_symbol_and_clears_after_review(self):
        self.write('nova_body/nova_demo/a.py', 'def f():\n    return 1\n\ndef g():\n    return 2\n')
        self.write('general_tools/architecture_map/notes/demo.md',
                   '---\ndoc: OPERATIONS.md\norder: 5\n---\n## Demo note\n\nDescribes f.\n')
        self.write('general_tools/architecture_map/reviews.json', json.dumps({'schema': 1, 'sections': {
            'OPERATIONS.md#Demo note': {'watch': ['nova_body/nova_demo/a.py::f']}}}))
        mark_reviewed(self.root, ['OPERATIONS.md#Demo note'], today='2026-01-02')
        refresh(self.root)
        self.assertIn('## Demo note', self.read('OPERATIONS.md'))
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))
        # An unrelated function in the same file changes: no false alarm.
        self.write('nova_body/nova_demo/a.py', 'def f():\n    return 1\n\ndef g():\n    return 3\n')
        refresh(self.root)
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))
        # The described function changes: the section says so, and names the reason.
        self.write('nova_body/nova_demo/a.py', 'def f():\n    return 9\n\ndef g():\n    return 3\n')
        refresh(self.root)
        ops = self.read('OPERATIONS.md')
        self.assertIn('Review needed', ops)
        self.assertIn('nova_body/nova_demo/a.py::f', ops)
        self.assertIn('2026-01-02', ops)
        mark_reviewed(self.root, ['OPERATIONS.md#Demo note'])
        refresh(self.root)
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))
        # An editor flipping line endings is not a change to what the section describes.
        path = self.root / 'nova_body/nova_demo/a.py'
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        refresh(self.root)
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))

    def test_provenance_line_no_longer_claims_the_prose_was_generated(self):
        self.write('nova_body/nova_demo/a.py', 'pass\n')
        refresh(self.root)
        readme = self.read('README.md')
        self.assertIn('Facts regenerated', readme)
        self.assertIn('Explanations carry their own review dates', readme)
        self.assertNotIn('_Generated ', readme)

    def test_watcher_timestamp_alone_does_not_invalidate_whole_file_review(self):
        self.write('nova_body/nova_demo/a.py', '# Last updated: 2026-10-01\ndef f():\n    return 1\n')
        self.write('general_tools/architecture_map/reviews.json', json.dumps({'schema':1,'sections':{
            'OPERATIONS.md#Configuration and evidence':{'watch':['nova_body/nova_demo/a.py']}}}))
        mark_reviewed(self.root,['OPERATIONS.md#Configuration and evidence'])
        self.write('nova_body/nova_demo/a.py', '# Last updated: 2026-10-02\ndef f():\n    return 1\n')
        refresh(self.root)
        self.assertNotIn('Review needed',self.read('OPERATIONS.md'))

    def test_dangling_references_are_reported_and_fail_the_check(self):
        for rel in ('Orient/Architecture/index.html', 'Orient/Architecture/evidence/2026-10-01-autonomy.md',
                    'Orient/Architecture/evidence/2026-10-02-modernization.md',
                    'Orient/Architecture/Calls_Order.md'):
            self.write(rel, 'fixture')
        self.write('general_tools/pointer.py', '# see ' + 'Orient' + '/' + 'GONE.md\n')
        refresh(self.root)
        self.assertIn('GONE.md', self.read('OPERATIONS.md'))
        self.assertEqual(check(self.root), 1)
        self.write('general_tools/pointer.py', '# see ' + 'Orient' + '/OPERATIONS.md#nowhere\n')
        refresh(self.root)
        self.assertIn('no such heading', self.read('OPERATIONS.md'))
        self.write('general_tools/pointer.py', '# see ' + 'Orient' + '/OPERATIONS.md#orient-health\n')
        refresh(self.root)
        self.assertIn('**Dangling references:** none.', self.read('OPERATIONS.md'))
        self.assertEqual(check(self.root), 0)
        self.write('general_tools/pointer.py', '# changed after publishing\n')
        self.assertEqual(check(self.root), 1)   # stale until regenerated

    def test_index_groups_root_files_once_describes_files_and_separates_backups(self):
        self.write('NovaStart.cmd', '@echo off\nREM Launch the whole stack\n')
        self.write('nova_start.py', '# @nova: Starts every service in order.\n')
        self.write('nova_body/nova_demo/a.py', '"""Demo faculty."""\n')
        self.write('nova_body/nova_demo/a.py.turnabout_bak', 'old\n')
        self.write('nova_body/SELF/core/me.md', '# A private title\n')
        refresh(self.root)
        index = self.read('INDEX.md')
        self.assertEqual(index.count('## Project entry points'), 1)
        self.assertLess(index.index('nova_start.py'), index.index('## nova_body'))
        for text in ('Starts every service in order.', 'Demo faculty.', 'Launch the whole stack'):
            self.assertIn(text, index)
        self.assertNotIn('A private title', index)
        canonical, _, backups = index.partition('## Backup copies')
        self.assertNotIn('turnabout_bak', canonical)
        self.assertIn('turnabout_bak', backups)

    def test_derived_tables_new_faculties_and_note_placement(self):
        self.write('nova_body/nova_cortex/tunables.py',
                   'REGISTRY: dict = {"k": {"default": 3, "type": "int", "min": 1, "max": 9, '
                   '"label": "Knob K", "desc": "d", "category": "Cognition"}}\n')
        self.write('nova_body/Nova_Created/nova_body/tools/demo_tool.py',
                   'TOOL = {"name": "demo_tool", "description": "Does a demo.", "params": {}, "version": 1}\n'
                   'def run(**a):\n    return "ok"\n')
        self.write('nova_body/Nova_Created/nova_body/tests/demo_tool.py', 'CASES = []\n')
        self.write('general_tools/architecture_map/notes/t.md', '---\ndoc: OPERATIONS.md\n---\n## Knobs\n\n{{TUNABLES_TABLE}}\n')
        self.write('general_tools/architecture_map/notes/s.md', '---\ndoc: ARCHITECTURE.md\n---\n## Shelf\n\n{{SHELF_TABLE}}\n')
        self.write('nova_body/nova_brandnew/x.py', 'pass\n')
        refresh(self.root)
        ops, arch = self.read('OPERATIONS.md'), self.read('ARCHITECTURE.md')
        self.assertIn('| `k` | Knob K | Cognition | `3` | 1\u20139 |', ops)
        self.assertIn('Does a demo.', arch)
        self.assertIn('| yes |', arch)
        self.assertIn('`nova_brandnew`', arch)
        self.assertIn('New since this table was written', arch)
        self.assertLess(arch.index('## Shelf'), arch.index('## Statically registered tools'))
        self.assertLess(ops.index('## Knobs'), ops.index('## Declared interface routes'))
        self.assertNotIn('{{', ops + arch)
        # Editing a note republishes even though no Python source changed.
        self.write('general_tools/architecture_map/notes/t.md', '---\ndoc: OPERATIONS.md\n---\n## Knobs\n\nEdited.\n')
        self.assertTrue(refresh(self.root)['changed'])

    def test_a_watcher_stamp_above_the_front_matter_neither_moves_nor_leaks_a_note(self):
        # nova_sync's watcher puts "_Last updated: ..._" on line 1 of any .md it sees change, above
        # the front matter, and Windows rewrites the file with CRLF.
        self.write('general_tools/architecture_map/notes/s.md',
                   '_Last updated: 2026-10-02 23:08:51_\r\n---\r\ndoc: ARCHITECTURE.md\r\norder: 5\r\n'
                   '---\r\n## Shelf\r\n\r\nStamped note body.\r\n')
        refresh(self.root)
        ops, arch = self.read('OPERATIONS.md'), self.read('ARCHITECTURE.md')
        self.assertIn('Stamped note body.', arch)
        self.assertNotIn('Stamped note body.', ops)
        self.assertNotIn('_Last updated', arch)
        self.assertNotIn('doc: ARCHITECTURE.md', arch)

    def test_a_watcher_restamp_alone_never_flags_a_reviewed_file(self):
        stamped = '# Last updated: 2026-10-01 11:51:33\nX = 1\n'
        self.write('nova_body/nova_demo/w.py', stamped)
        self.write('general_tools/architecture_map/notes/w.md',
                   '---\ndoc: OPERATIONS.md\n---\n## Whole file\n\nDescribes w.\n')
        # A baseline recorded before stamps were ignored (stamp included in the digest) still counts.
        self.write('general_tools/architecture_map/reviews.json', json.dumps({'schema': 1, 'sections': {
            'OPERATIONS.md#Whole file': {'reviewed': '2026-10-01', 'watch': ['nova_body/nova_demo/w.py'],
                                         'baseline': {'nova_body/nova_demo/w.py':
                                                      hashlib.sha256(stamped.encode()).hexdigest()}}}}))
        refresh(self.root)
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))
        mark_reviewed(self.root, ['OPERATIONS.md#Whole file'], today='2026-10-02')
        # The watcher restamps the header and nothing else changes.
        self.write('nova_body/nova_demo/w.py', '# Last updated: 2026-10-01 20:18:21\nX = 1\n')
        refresh(self.root)
        self.assertNotIn('Review needed', self.read('OPERATIONS.md'))
        # A real change still flags the section.
        self.write('nova_body/nova_demo/w.py', '# Last updated: 2026-10-01 20:18:21\nX = 2\n')
        refresh(self.root)
        self.assertIn('Review needed', self.read('OPERATIONS.md'))

    def test_purpose_lines_describe_files_and_files_without_one_are_listed(self):
        self.write('nova_body/nova_demo/spec.md', '# Title\n<!-- @nova: Contract for demo experts. -->\n')
        self.write('nova_body/nova_demo/plain.md', '# Personal-looking title\n')
        self.write('nova_body/nova_demo/style.css', '/* @nova: Styles the demo page. */\nbody {}\n')
        self.write('nova_body/nova_demo/tool.py', 'TOOL = {"name": "t", "description": "Counts things."}\n')
        self.write('nova_body/nova_demo/bare.py', 'X = 1\n')
        self.write('nova_body/nova_demo/data.json', '{}\n')
        self.write('nova_body/Nova_Created/nova_night_notes/night.md', '# A private night\n')
        self.write('general_tools/architecture_map/notes/n.md',
                   '---\ndoc: OPERATIONS.md\n---\n<!-- @nova: Orient note for the demo. -->\n## Demo section\n\nBody.\n')
        refresh(self.root)
        index, ops = self.read('INDEX.md'), self.read('OPERATIONS.md')
        for text in ('Contract for demo experts.', 'Styles the demo page.', 'Counts things.', 'Orient note for the demo.'):
            self.assertIn(text, index)
        self.assertNotIn('Personal-looking title', index)
        self.assertNotIn('A private night', index)
        listed = index.split('## Files without a purpose line', 1)[1].split('\n## ', 1)[0]
        self.assertIn('nova_demo/bare.py', listed)
        self.assertIn('nova_demo/plain.md', listed)
        for exempt in ('data.json', 'night.md', 'spec.md', 'tool.py', 'style.css', 'notes/n.md'):
            self.assertNotIn(exempt, listed)
        self.assertIn('**Files without a purpose line:** 2,', ops)
        self.assertIn('## Demo section', ops)
        self.assertNotIn('Orient note for the demo.', ops)

    def test_an_outdated_loaded_copy_never_overwrites_newer_output(self):
        # Nova Chat keeps the generator imported for days; after orient.py changes, its copy is old.
        self.write('nova_body/nova_demo/a.py', 'X = 1\n')
        with patch('orient._LOADED_CODE', 'digest of an older orient.py'):
            result = refresh(self.root)
        self.assertFalse(result['changed'])
        self.assertIn('skipped', result)
        self.assertFalse((self.root / 'Orient/INDEX.md').exists())
        self.assertTrue(refresh(self.root)['changed'])

    def test_ai_notes_are_listed_newest_first_and_misnamed_ones_flagged(self):
        self.write('nova_body/nova_demo/a.py', 'X = 1\n')
        self.write('Orient/AI Notes/ReadMeBeforeNoteTaking.md', '# Rules\n')
        self.write('Orient/AI Notes/2026-10-03_0955_Claude_OrientUpkeep.md', '# x\n')
        self.write('Orient/AI Notes/2026-10-03_1645_Codex_AutonomyUpdate.md', '# y\n')
        self.write('Orient/AI Notes/my notes.md', 'z\n')
        refresh(self.root)
        readme, ops = self.read('README.md'), self.read('OPERATIONS.md')
        self.assertLess(readme.index('2026-10-03_1645_Codex_AutonomyUpdate.md'),
                        readme.index('2026-10-03_0955_Claude_OrientUpkeep.md'))
        self.assertIn('`my notes.md`', ops)
        dangling = json.loads((self.root / 'Orient/Architecture/inventory.json').read_text())['dangling']
        self.assertFalse([d for d in dangling if 'AI' in d[2]])   # links into AI Notes resolve
        # A new note republishes the README although no source changed; notes are never touched.
        self.write('Orient/AI Notes/2026-10-03_1700_Claude_Followup.md', '# z\n')
        self.assertTrue(refresh(self.root)['changed'])
        self.assertIn('2026-10-03_1700_Claude_Followup.md', self.read('README.md'))
        self.assertTrue((self.root / 'Orient/AI Notes/my notes.md').exists())

    def test_a_null_damaged_source_is_reported_instead_of_crashing_the_refresh(self):
        self.write('nova_body/nova_demo/ok.py', 'pass\n')
        (self.root / 'nova_body/nova_demo/bad.py').write_bytes(b'# header\n' + b'\x00' * 64 + b'x = 1\n')
        refresh(self.root)
        self.assertIn('Damaged sources', self.read('OPERATIONS.md'))
        self.assertIn('nova_demo/bad.py', self.read('OPERATIONS.md'))
        self.assertEqual(check(self.root), 1)


if __name__ == '__main__':
    unittest.main()
