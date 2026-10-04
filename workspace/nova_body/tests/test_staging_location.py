# Last updated: 2026-10-04 14:59:16
# @nova: Guards where task workspaces are staged: under workspace/Temp, outside git, Orient and the sync watcher.
"""Staged task copies must live where git, Orient and the watcher never look (2026-10-03)."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_cortex import tasking


class StagingLocation(unittest.TestCase):
    def test_copies_are_staged_under_temp(self):
        from nova_cortex import task_workspace as ws
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for target, value in [('nova_cortex.tasking._STORE', root / 'tasks.json'),
                              ('nova_cortex.task_workspace.WORKSPACE_ROOT', root),
                              ('nova_cortex.task_workspace.workspace_path', lambda p: root / p),
                              ('nova_cortex.task_workspace.body_path', lambda *p: root.joinpath('body', *p))]:
            p = patch(target, value); p.start(); self.addCleanup(p.stop)
        (root / 'code').mkdir()
        (root / 'code' / 'a.py').write_text('x = 1\n')
        tid = tasking.create('stage me')
        plan = ws.prepare(tid, ['code'])
        self.assertTrue(plan['directory'].startswith('Temp/task-workspaces/' + tid + '/'))
        self.assertNotIn('Tasking', Path(plan['directory']).parts)
        self.assertTrue((root / plan['directory'] / 'code' / 'a.py').is_file())


if __name__ == '__main__':
    unittest.main()
