# @nova: Guards the watcher and git rules that keep agent transport, task copies, avatar files and the work queue out of autosave.
"""Exclusion rules shared by the sync watcher and workspace/.gitignore (2026-10-03)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]  # workspace/
sys.path.insert(0, str(ROOT / 'general_tools'))


class Exclusions(unittest.TestCase):
    def test_watcher_skips_private_temp_areas(self):
        from nova_sync import watcher
        for sub in ('Temp/collaboration', 'Temp/task-workspaces'):
            self.assertIn(sub, watcher.EXCLUDE_SUBPATHS)

    def test_gitignore_excludes_temp_avatar_and_work_queue(self):
        rules = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        for rule in ('**/Temp/', 'nova_body/SELF/Avatar/', 'nova_body/memory/runtime_work.sqlite3*'):
            self.assertIn(rule, rules)


if __name__ == '__main__':
    unittest.main()
