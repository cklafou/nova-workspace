# Last updated: 2026-10-05 21:27:11
# @nova: Checks restart reporting against real edits and harmless watcher timestamp changes.
import os
from pathlib import Path
import tempfile
import unittest
from general_tools.nova_chat.tests.test_controller_repair import functions, ROOT

class FingerprintTests(unittest.TestCase):
    def test_real_same_size_same_timestamp_edit_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'code.py';p.write_text('VALUE = 1\n');stamp=p.stat()
            ns=functions(ROOT/'general_tools/nova_chat/server.py',{'_fingerprint_now'},{'_INBOX_WORKSPACE':root,'_CODE_FILES':['code.py']})
            first=ns['_fingerprint_now']()
            p.write_text('VALUE = 2\n');os.utime(p,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            self.assertNotEqual(first,ns['_fingerprint_now']())
    def test_timestamp_stamp_and_line_endings_are_not_code_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'code.py';p.write_bytes(b'# Last updated: 2026-10-01 12:00:00\nVALUE = 1\n')
            ns=functions(ROOT/'general_tools/nova_chat/server.py',{'_fingerprint_now'},{'_INBOX_WORKSPACE':root,'_CODE_FILES':['code.py']})
            first=ns['_fingerprint_now']()
            p.write_bytes(b'# Last updated: 2026-10-03 13:30:30\r\nVALUE = 1\r\n')
            self.assertEqual(first,ns['_fingerprint_now']())
