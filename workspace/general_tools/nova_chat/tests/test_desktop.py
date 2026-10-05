# @nova: Verify native controller geometry across processes and preserve renderer storage during isolated profile migration.
# Last updated: 2026-10-05 21:27:11
"""Run: python -m unittest discover -s general_tools/nova_chat/tests.

Tests the desktop face without importing Nova's runtime or loading a model.
"""
import importlib.util
import os
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from PyQt6.QtCore import QCoreApplication, QEvent, QSettings
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEngineProfile

spec = importlib.util.spec_from_file_location('nova_desktop', Path(__file__).parents[1] / 'desktop.py')
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['NovaControllerTests'])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / 'window.ini'), QSettings.Format.IniFormat)
        self.profile = QWebEngineProfile(self.app)
        self.tray_patch = patch.object(desktop.QSystemTrayIcon, 'isSystemTrayAvailable', return_value=False)
        self.tray_patch.start()
        self.addCleanup(self.tray_patch.stop)
        self.window = desktop.Controller(self.profile, self.settings)
        self.extra_windows = []

    def tearDown(self):
        for window in [self.window, *self.extra_windows]:
            window.quitting = True
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.profile.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.temp.cleanup()

    def test_popup_uses_same_persistent_profile(self):
        view = self.window.view.createWindow(None)
        popup = view.window()
        self.assertIs(view.page().profile(), self.profile)
        self.assertTrue(popup.popup)
        self.assertIsNone(popup.tray)
        popup.close()
        self.assertNotIn(popup, desktop.WINDOWS)

    def test_window_geometry_restores(self):
        self.window.resize(640, 480)
        self.window.save_window()
        fresh = QSettings(self.settings.fileName(), QSettings.Format.IniFormat)
        other = desktop.Controller(self.profile, fresh)
        self.assertEqual(other.size().width(), 640)
        self.assertEqual(other.size().height(), 480)
        other.quitting = True
        other.close()
        other.deleteLater()

    def test_desktop_has_native_navigation(self):
        self.assertEqual([action.text() for action in self.window.menuBar().actions()], ['Nova', 'View'])
        self.assertIs(self.window.centralWidget(), self.window.view)

    def restore(self):
        other = desktop.Controller(self.profile, QSettings(self.settings.fileName(), QSettings.Format.IniFormat))
        self.extra_windows.append(other)
        return other

    def test_resize_and_move_events_persist_without_closing_the_window(self):
        self.window.show()
        self.app.processEvents()
        self.window.resize(620, 470)
        self.window.move(55, 70)
        self.app.processEvents()
        QTest.qWait(450)
        other = self.restore()
        self.assertEqual((other.width(), other.height()), (620, 470))
        self.assertLess(abs(other.x() - self.window.x()), 5)
        self.assertLess(abs(other.y() - self.window.y()), 5)

    def test_minimizing_keeps_the_last_normal_geometry(self):
        self.window.show()
        self.app.processEvents()
        self.window.resize(630, 475)
        self.app.processEvents()
        self.window.showMinimized()
        self.app.processEvents()
        self.window.save_window()
        other = self.restore()
        self.assertFalse(other.isMinimized())
        self.assertEqual((other.width(), other.height()), (630, 475))

    def test_maximized_state_and_restore_size_survive_reopening(self):
        self.window.show()
        self.window.resize(650, 480)
        self.app.processEvents()
        self.window.showMaximized()
        self.app.processEvents()
        self.window.save_window()
        other = self.restore()
        self.assertTrue(other.isMaximized())
        other.showNormal()
        self.app.processEvents()
        self.assertEqual((other.width(), other.height()), (650, 480))

    def test_tray_close_saves_immediately_and_popup_cannot_overwrite_it(self):
        self.window.show()
        self.window.resize(610, 465)
        self.app.processEvents()
        self.window.tray = Mock()
        self.window.close()
        self.assertFalse(self.window.isVisible())
        self.window.tray.showMessage.assert_called_once()
        popup = desktop.Controller(self.profile, self.settings, popup=True)
        self.extra_windows.append(popup)
        popup.resize(740, 520)
        popup.save_window()
        other = self.restore()
        self.assertEqual((other.width(), other.height()), (610, 465))

    def test_application_quit_flushes_a_resize_before_the_debounce_fires(self):
        self.window.show()
        self.window.resize(625, 475)
        self.app.processEvents()
        self.window.geometry_timer.stop()
        self.app.aboutToQuit.emit()
        other = self.restore()
        self.assertEqual((other.width(), other.height()), (625, 475))

    def test_saved_geometry_is_clamped_when_the_old_screen_is_unavailable(self):
        self.window.move(30000, 30000)
        self.window.save_window()
        other = self.restore()
        self.assertTrue(self.app.primaryScreen().availableGeometry().contains(other.frameGeometry().center()))

    def test_settings_write_error_is_visible_instead_of_silently_losing_size(self):
        bad = Mock()
        bad.status.return_value = QSettings.Status.AccessError
        bad.fileName.return_value = str(Path(self.temp.name) / 'blocked.ini')
        self.window.settings = bad
        with patch('sys.stderr'):
            self.window.save_window()
        self.assertIn('could not be saved', self.window.statusBar().currentMessage())
        self.assertIn('AccessError', self.window._settings_error)
        self.window.settings = self.settings

    def test_geometry_round_trip_uses_two_fresh_offscreen_processes(self):
        # Writer exits without Qt close/quit hooks; event-triggered sync must already be durable.
        code = r"""
import importlib.util,json,os,sys
from pathlib import Path
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtTest import QTest
spec=importlib.util.spec_from_file_location('fixture_desktop',sys.argv[1])
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
app=QApplication(['OffscreenGeometryFixture'])
d.QSystemTrayIcon.isSystemTrayAvailable=lambda:False
settings=QSettings(sys.argv[2],QSettings.Format.IniFormat)
profile=QWebEngineProfile(app)
window=d.Controller(profile,settings)
if sys.argv[3]=='write':
    window.show();app.processEvents()
    window.resize(660,485);window.move(50,65);app.processEvents();QTest.qWait(450)
else:
    print(json.dumps({'width':window.width(),'height':window.height(),'x':window.x(),'y':window.y()}),flush=True)
os._exit(0)
"""
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QTWEBENGINE_CHROMIUM_FLAGS='--disable-gpu')
        source = str(Path(__file__).parents[1] / 'desktop.py')
        settings = str(Path(self.temp.name) / 'cross-process.ini')
        writer = subprocess.run([sys.executable, '-c', code, source, settings, 'write'], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(writer.returncode, 0, writer.stderr)
        reader = subprocess.run([sys.executable, '-c', code, source, settings, 'read'], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(reader.returncode, 0, reader.stderr)
        state = json.loads(reader.stdout.strip())
        self.assertEqual((state['width'], state['height']), (660, 485))
        self.assertLess(abs(state['x'] - 50), 5)
        self.assertLess(abs(state['y'] - 65), 5)


class ProfileMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.appdata = self.root / 'legacy-appdata'
        self.legacy = self.appdata / 'ProjectNova/Controller'
        self.legacy.mkdir(parents=True)
        (self.legacy / 'window.ini').write_bytes(b'fixture geometry')
        (self.legacy / 'storage/Local Storage/leveldb').mkdir(parents=True)
        (self.legacy / 'storage/Local Storage/leveldb/fixture.ldb').write_bytes(b'named user layout')
        (self.legacy / 'cache').mkdir()
        (self.legacy / 'cache/disposable').write_bytes(b'cache')
        self.home_patch = patch.object(desktop.Path, 'home', return_value=self.home)
        self.env_patch = patch.dict(os.environ, {'LOCALAPPDATA':str(self.appdata)})
        self.home_patch.start();self.env_patch.start()
        self.addCleanup(self.home_patch.stop);self.addCleanup(self.env_patch.stop)

    def test_first_real_caller_copy_preserves_geometry_layouts_and_original(self):
        base = desktop.controller_profile_dir()
        self.assertEqual(base, self.home / 'ProjectNovaData/Controller')
        self.assertEqual((base / 'window.ini').read_bytes(), b'fixture geometry')
        self.assertEqual((base / 'storage/Local Storage/leveldb/fixture.ldb').read_bytes(), b'named user layout')
        self.assertFalse((base / 'cache').exists())
        self.assertEqual((self.legacy / 'window.ini').read_bytes(), b'fixture geometry')
        self.assertTrue((self.legacy / 'storage/Local Storage/leveldb/fixture.ldb').is_file())
        self.assertTrue(json.loads((base / 'profile-migration.json').read_text())['legacy_preserved'])

    def test_another_launch_environment_cannot_select_or_overwrite_a_different_profile(self):
        base = desktop.controller_profile_dir()
        (base / 'window.ini').write_bytes(b'new saved geometry')
        with patch.dict(os.environ, {'LOCALAPPDATA':str(self.root / 'different-virtualized-appdata')}):
            self.assertEqual(desktop.controller_profile_dir(), base)
        self.assertEqual((base / 'window.ini').read_bytes(), b'new saved geometry')

    def test_failed_copy_never_publishes_a_blank_profile_or_removes_original(self):
        with patch.object(desktop.shutil, 'copytree', side_effect=PermissionError('fixture locked profile')):
            with self.assertRaisesRegex(OSError, 'original profile is preserved'):
                desktop.controller_profile_dir()
        self.assertFalse((self.home / 'ProjectNovaData/Controller').exists())
        self.assertTrue((self.legacy / 'window.ini').is_file())
        self.assertTrue((self.legacy / 'storage/Local Storage/leveldb/fixture.ldb').is_file())

    def test_explicit_preview_profile_does_not_import_any_user_settings(self):
        preview = self.root / 'preview'
        with patch.object(desktop.Path, 'home', side_effect=AssertionError('preview consulted user profile')):
            self.assertEqual(desktop.controller_profile_dir(preview), preview)
        self.assertEqual(list(preview.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
