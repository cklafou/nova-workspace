# @nova: Verify queued/running conversation pins preserve complete transcripts across session switches using disposable files.
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from datetime import datetime

CHAT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SessionPinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'sessions'
        self.transcripts = load('isolated_pin_transcript', CHAT / 'transcript.py')
        self.transcripts.LOG_DIR = self.directory
        with patch.dict(sys.modules, {'nova_chat.transcript': self.transcripts}):
            self.module = load('isolated_pin_manager', CHAT / 'session_manager.py')
        self.module.SESSIONS_DIR = self.directory
        self.module.INDEX_PATH = self.directory / 'sessions_index.json'
        self.manager = self.module.SessionManager()
        self.a = self.manager.active_id
        self.original = self.manager.active
        self.original.add('Cole', 'original request')
        self.manager.update_meta_from_message(self.original.messages[-1])

    def contents(self, path):
        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                lines = stream.readlines()
        else:
            lines = path.read_text(encoding='utf-8').splitlines()
        return [json.loads(line)['content'] for line in lines if line.strip()]

    def test_queued_request_finishes_after_switch_without_tail_only_log(self):
        self.assertTrue(self.manager.retain(self.a, self.original))
        self.assertTrue(self.manager.retain(self.a, self.original))
        self.b = self.manager.new_session('other conversation')
        self.assertNotEqual(self.a, self.b)
        self.assertTrue(self.manager._jsonl_path(self.a).exists())
        self.assertFalse(self.manager._gz_path(self.a).exists())
        final = self.original.add('Nova', 'reply to original request')
        self.manager.update_meta_from_message(final, session_id=self.a, transcript=self.original)
        self.assertEqual(self.manager._index[self.a].message_count, 2)
        self.assertEqual(self.manager._index[self.b].message_count, 0)
        self.assertTrue(self.manager.release(self.a, self.original))
        self.assertTrue(self.manager._jsonl_path(self.a).exists())
        self.assertTrue(self.manager.release(self.a, self.original))
        self.assertFalse(self.manager._jsonl_path(self.a).exists())
        self.assertEqual(self.contents(self.manager._gz_path(self.a)),
                         ['original request', 'reply to original request'])
        self.assertTrue(self.manager.switch_session(self.a))
        self.assertEqual([m['content'] for m in self.manager.active.messages],
                         ['original request', 'reply to original request'])

    def test_switch_back_reuses_live_object_before_reply_then_flush_preserves_it(self):
        self.assertTrue(self.manager.retain(self.a, self.original))
        b = self.manager.new_session('other')
        self.assertTrue(self.manager.switch_session(self.a))
        self.assertIs(self.manager.active, self.original)
        self.original.add('Nova', 'late final')
        self.assertEqual(self.manager.active.messages[-1]['content'], 'late final')
        self.assertTrue(self.manager.release(self.a, self.original))
        self.assertTrue(self.manager._jsonl_path(self.a).exists())
        self.manager.switch_session(b)
        self.manager.switch_session(self.a)
        self.assertEqual([m['content'] for m in self.manager.active.messages],
                         ['original request', 'late final'])

    def test_pinned_inactive_session_cannot_be_archived_or_deleted(self):
        self.manager.retain(self.a, self.original)
        self.manager.new_session('other')
        self.assertFalse(self.manager.delete_session(self.a))
        self.assertFalse(self.manager.archive_session(self.a))
        self.manager.release(self.a, self.original)
        self.assertTrue(self.manager.archive_session(self.a))
        archive = self.directory / 'archives' / self.manager._gz_path(self.a).name
        self.assertEqual(self.contents(archive), ['original request'])

    def test_wrong_identity_and_duplicate_release_cannot_unpin_real_work(self):
        stale = self.transcripts.Transcript(session_id=self.a)
        self.assertFalse(self.manager.retain(self.a, stale))
        self.assertFalse(self.manager.retain('missing', self.original))
        self.assertTrue(self.manager.retain(self.a, self.original))
        self.assertFalse(self.manager.release(self.a, stale))
        self.manager.new_session('other')
        self.assertFalse(self.manager.delete_session(self.a))
        self.assertTrue(self.manager.release(self.a, self.original))
        self.assertFalse(self.manager.release(self.a, self.original))
        self.assertFalse(self.manager.retain(self.a, self.original))

    def test_failed_gzip_publication_keeps_complete_raw_log(self):
        self.manager.retain(self.a, self.original)
        self.manager.new_session('other')
        self.original.add('Nova', 'late final')
        actual_replace = self.module.os.replace
        def fail_gzip(source, dest):
            if str(dest).endswith('.gz'):
                raise OSError('fixture disk publication failure')
            return actual_replace(source, dest)
        with patch.object(self.module.os, 'replace', side_effect=fail_gzip):
            self.assertTrue(self.manager.release(self.a, self.original))
        self.assertEqual(self.contents(self.manager._jsonl_path(self.a)), ['original request', 'late final'])
        self.assertFalse(self.manager._gz_path(self.a).exists())
        self.assertFalse(list(self.directory.glob('*.tmp')))
        self.manager.switch_session(self.a)
        self.assertEqual(len(self.manager.active.messages), 2)

    def test_new_sessions_same_second_have_distinct_identity(self):
        fixed = datetime(2026, 10, 5, 21, 55, 0)
        with patch.object(self.module, 'datetime', types.SimpleNamespace(now=lambda: fixed)):
            first = self.manager.new_session('first')
            self.manager.active.add('Cole', 'first distinct content')
            second = self.manager.new_session('second')
            self.manager.active.add('Cole', 'second distinct content')
        self.assertNotEqual(first, second)
        self.manager.switch_session(first)
        self.assertEqual(self.manager.active.messages[0]['content'], 'first distinct content')
        self.manager.switch_session(second)
        self.assertEqual(self.manager.active.messages[0]['content'], 'second distinct content')


if __name__ == '__main__':
    unittest.main()
