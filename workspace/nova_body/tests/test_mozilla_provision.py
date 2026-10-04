# @nova: Verify pinned browser provisioning with disposable files and no network, account changes or application launches.
import hashlib
import io
import json
import re
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "nova_computer/provision/setup_guest.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8").split("<<'MOZILLA_PY'", 1)[1].split("\n", 1)[1].split("\nMOZILLA_PY", 1)[0]


class MozillaProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:xz") as archive:
            payload = b"disposable executable fixture"
            item = tarfile.TarInfo("firefox/firefox")
            item.size = len(payload)
            archive.addfile(item, io.BytesIO(payload))
        self.archive = data.getvalue()
        self.source = re.sub(r'SHA256 = "[a-f0-9]+"', 'SHA256 = "' + hashlib.sha256(self.archive).hexdigest() + '"', SOURCE)
        self.link = self.home / '.local/bin/firefox'
        self.target = self.home / '.local/opt/mozilla-firefox-157.0'

    def execute(self, source=None, download=None):
        # Windows need not permit real symlinks for installer logic fixtures. The real
        # guest symlink was verified separately; here retain its target as fixture bytes.
        def fixture_link(path, target):
            path.write_text(str(target), encoding='utf-8')
        with patch('pathlib.Path.home', return_value=self.home), \
             patch('urllib.request.urlopen', return_value=io.BytesIO(self.archive)) as network, \
             patch('subprocess.run', return_value=types.SimpleNamespace(returncode=0, stdout='Mozilla Firefox fixture', stderr='')) as run, \
             patch('pathlib.Path.symlink_to', fixture_link):
            if download is not None:
                network.return_value = io.BytesIO(download)
            exec(compile(source or self.source, str(SCRIPT), 'exec'), {})
        return network, run

    def test_verified_archive_selects_browser_and_records_source(self):
        network, run = self.execute()
        self.assertEqual(self.link.read_text(), str(self.target / 'firefox'))
        receipt = json.loads((self.target / 'nova-install.json').read_text())
        self.assertEqual(receipt['sha256'], hashlib.sha256(self.archive).hexdigest())
        self.assertIn('https://archive.mozilla.org/pub/firefox/releases/157.0/', receipt['source'])
        self.assertEqual(run.call_args.args[0][-1], '--version')
        self.assertFalse(list(self.target.parent.glob('.mozilla-install-*')))

    def test_unknown_launcher_is_preserved_before_any_network(self):
        self.link.parent.mkdir(parents=True)
        self.link.write_text('user launcher')
        with patch('pathlib.Path.home', return_value=self.home), patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(RuntimeError, 'Preserving existing user Firefox launcher'):
                exec(compile(self.source, str(SCRIPT), 'exec'), {})
            network.assert_not_called()
        self.assertEqual(self.link.read_text(), 'user launcher')

    def test_checksum_failure_cannot_install_or_select_browser(self):
        with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
            self.execute(download=b'corrupt archive')
        self.assertFalse(self.target.exists())
        self.assertFalse(self.link.exists())
        self.assertFalse(list(self.target.parent.glob('.mozilla-install-*')))

    def test_existing_selected_version_does_not_download_or_overwrite(self):
        (self.target / 'firefox').parent.mkdir(parents=True)
        (self.target / 'firefox').write_text('existing browser')
        self.link.parent.mkdir(parents=True)
        self.link.write_text('link fixture')
        original_resolve = Path.resolve
        original_symlink = Path.is_symlink
        def resolve(path, *a, **kw):
            return self.target / 'firefox' if path == self.link else original_resolve(path, *a, **kw)
        def symlink(path):
            return path == self.link or original_symlink(path)
        with patch('pathlib.Path.home', return_value=self.home), patch('pathlib.Path.resolve', resolve), \
             patch('pathlib.Path.is_symlink', symlink), patch('urllib.request.urlopen') as network:
            with self.assertRaises(SystemExit) as stopped:
                exec(compile(self.source, str(SCRIPT), 'exec'), {})
            self.assertEqual(stopped.exception.code, 0)
            network.assert_not_called()
        self.assertEqual((self.target / 'firefox').read_text(), 'existing browser')


if __name__ == '__main__':
    unittest.main()
