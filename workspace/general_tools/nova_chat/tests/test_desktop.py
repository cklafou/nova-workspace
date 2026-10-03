# Last updated: 2026-10-03 10:59:53
"""Run: python -m unittest discover -s general_tools/nova_chat/tests.

Tests the desktop face without importing Nova's runtime or loading a model.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEngineProfile

spec = importlib.util.spec_from_file_location('nova_desktop', Path(__file__).parents[1] / 'desktop.py')
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['NovaControllerTests'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / 'window.ini'), QSettings.Format.IniFormat)
        self.profile = QWebEngineProfile(self.app)
        self.window = desktop.Controller(self.profile, self.settings)

    def tearDown(self):
        self.window.quitting = True
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
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
        other = desktop.Controller(self.profile, self.settings)
        self.assertEqual(other.size().width(), 640)
        self.assertEqual(other.size().height(), 480)
        other.quitting = True
        other.close()
        other.deleteLater()

    def test_desktop_has_native_navigation(self):
        self.assertEqual([action.text() for action in self.window.menuBar().actions()], ['Nova', 'View'])
        self.assertIs(self.window.centralWidget(), self.window.view)


if __name__ == '__main__':
    unittest.main()
