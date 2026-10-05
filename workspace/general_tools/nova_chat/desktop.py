# @nova: Host Nova Chat in persistent native windows with a stable renderer profile and saved window geometry.
# Last updated: 2026-10-06 03:19:20
"""Nova desktop face: native windows, menus, tray and persistent renderer profile.

Run with --url for an isolated UI preview. NovaStart owns the runtime processes;
this module never imports Nova's body or starts inference.
"""
from __future__ import annotations

import argparse
import os
import json
import shutil
import tempfile
import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QSettings, QUrl, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QMessageBox, QSystemTrayIcon
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView


def controller_profile_dir(explicit=None) -> Path:
    """Choose one non-virtualized home; migrate only in this actual desktop caller.

    Copy window settings and Chromium storage together so layouts/localStorage survive.
    The old profile remains untouched, cache is disposable, and an incomplete copy is
    never published as the new profile. Preview profiles never import the user's data.
    """
    if explicit is not None:
        base = Path(explicit).expanduser()
        base.mkdir(parents=True, exist_ok=True)
        return base
    base = Path.home() / 'ProjectNovaData' / 'Controller'
    if base.is_dir():
        return base
    if base.exists():
        raise OSError(f'The controller profile path is not a directory: {base}')
    legacy = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ProjectNova' / 'Controller'
    base.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.Controller-migration-', dir=base.parent))
    try:
        if legacy.is_dir():
            settings = legacy / 'window.ini'
            if settings.is_file():
                shutil.copy2(settings, stage / settings.name)
            storage = legacy / 'storage'
            if storage.is_dir():
                shutil.copytree(storage, stage / 'storage')
            (stage / 'profile-migration.json').write_text(json.dumps({
                'version': 1, 'source': str(legacy), 'legacy_preserved': True,
                'copied': [name for name in ('window.ini', 'storage') if (stage / name).exists()]
            }, indent=2) + '\n', encoding='utf-8')
        if base.exists():
            raise OSError('Another controller created the destination during profile migration; reopen Nova Chat.')
        os.rename(stage, base)
        return base
    except Exception as error:
        raise OSError(f'Controller settings could not be migrated. The original profile is preserved at {legacy}. '
                      f'Close any other Nova Chat windows and retry. Details: {error}') from error
    finally:
        # Only remove our unpublished staging directory, never either real profile.
        if stage.exists() and stage.resolve().parent == base.parent.resolve() \
                and stage.name.startswith('.Controller-migration-'):
            shutil.rmtree(stage)


def nova_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor('#18151f'))
    painter = QPainter(pixmap)
    painter.setPen(QColor('#c6a9ff'))
    font = painter.font()
    font.setPixelSize(46)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, '✦')
    painter.end()
    return QIcon(pixmap)


class NovaPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if (is_main_frame and navigation_type == self.NavigationType.NavigationTypeLinkClicked
                and url.scheme() in ('https', 'http') and url.host() not in ('127.0.0.1', 'localhost')):
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


class NovaView(QWebEngineView):
    def createWindow(self, window_type):
        child = Controller(self.window().profile, self.window().settings, popup=True)
        WINDOWS.append(child)
        child.show()
        return child.view


WINDOWS = []  # Keep Qt popup owners alive until their native windows close.


class Controller(QMainWindow):
    def __init__(self, profile, settings, popup=False):
        super().__init__()
        self.profile, self.settings, self.popup = profile, settings, popup
        self.quitting = False
        self._geometry_ready = False
        self._last_geometry = None
        self._settings_error = None
        self._load_ok = False
        self.geometry_timer = QTimer(self)
        self.geometry_timer.setSingleShot(True)
        self.geometry_timer.setInterval(350)
        self.geometry_timer.timeout.connect(self.save_window)
        self.setWindowTitle('Nova · Controller')
        self.setWindowIcon(nova_icon())
        self.resize(1500 if not popup else 900, 950 if not popup else 700)
        self.setMinimumSize(460, 380)
        self.view = NovaView(self)
        self.page = NovaPage(profile, self.view)
        self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        self.page.windowCloseRequested.connect(self.close)
        self.setCentralWidget(self.view)
        self.statusBar().showMessage('Connecting to Nova…')
        self.view.loadFinished.connect(self.loaded)
        self.page.renderProcessTerminated.connect(lambda *_: self.statusBar().showMessage('The interface stopped. Use View → Reload to reconnect.'))
        self.menuBar().setNativeMenuBar(True)
        app_menu = self.menuBar().addMenu('Nova')
        app_menu.addAction('Widget library', lambda: self.page.runJavaScript('window.novaWidgets?.()'))
        app_menu.addSeparator()
        app_menu.addAction('Quit Nova' if not popup else 'Close window', self.quit_app if not popup else self.close)
        view_menu = self.menuBar().addMenu('View')
        reload_action = QAction('Reload interface', self)
        reload_action.setShortcut('Ctrl+R')
        reload_action.triggered.connect(self.view.reload)
        view_menu.addAction(reload_action)
        view_menu.addAction('Zoom in', lambda: self.view.setZoomFactor(min(2, self.view.zoomFactor()+.1)))
        view_menu.addAction('Zoom out', lambda: self.view.setZoomFactor(max(.6, self.view.zoomFactor()-.1)))
        view_menu.addAction('Actual size', lambda: self.view.setZoomFactor(1))
        self.tray = None
        if not popup:
            geometry = settings.value('geometry')
            if geometry is not None:
                try:
                    self.restoreGeometry(geometry)  # Qt also clamps to available screen geometry.
                except (TypeError, ValueError):
                    pass  # Invalid legacy geometry falls back to the usable default size.
            self._last_geometry = self.saveGeometry()
            self._was_maximized = self.isMaximized()
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray = QSystemTrayIcon(self.windowIcon(), self)
                self.tray.setToolTip('Nova · Controller')
                menu = QMenu()
                menu.addAction('Show Nova', self.reveal)
                menu.addAction('Quit Nova', self.quit_app)
                self.tray_menu = menu
                self.tray.setContextMenu(menu)
                self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
                self.tray.show()
            QApplication.instance().aboutToQuit.connect(self.save_window)
        self._geometry_ready = True

    def loaded(self, ok):
        self._load_ok = ok
        if self._settings_error:
            self.statusBar().showMessage(self._settings_error)
            self.statusBar().show()
        elif ok:
            self.statusBar().hide()
        else:
            self.statusBar().showMessage('Nova’s interface is unavailable. Start Nova or use View → Reload to reconnect.')

    def _queue_geometry_save(self):
        if self.popup or not self._geometry_ready:
            return
        if not self.isMinimized():
            self._last_geometry = self.saveGeometry()
            self._was_maximized = self.isMaximized()
        self.geometry_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._queue_geometry_save()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._queue_geometry_save()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._queue_geometry_save()

    def save_window(self):
        if self.popup or not self._geometry_ready:
            return
        self.geometry_timer.stop()
        if not self.isMinimized():
            self._last_geometry = self.saveGeometry()
        if self._last_geometry is None:
            return
        self.settings.setValue('geometry', self._last_geometry)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            message = f'Window size could not be saved ({self.settings.status().name}): {self.settings.fileName()}'
            if message != self._settings_error:
                print(message, file=sys.stderr)
            self._settings_error = message
            self.statusBar().showMessage(message)
            self.statusBar().show()
        elif self._settings_error:
            self._settings_error = None
            if self._load_ok:
                self.statusBar().hide()

    def reveal(self):
        if getattr(self, '_was_maximized', False):
            self.showMaximized()
        else:
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.quitting = True
        self.save_window()
        for window in list(WINDOWS):
            window.quitting = True
            window.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        self.save_window()
        if not self.popup and not self.quitting and self.tray:
            event.ignore()
            self._was_maximized = self.isMaximized()
            self.hide()
            self.tray.showMessage('Nova is still running', 'Open Nova from the tray. Choose Quit Nova to shut down.')
            return
        event.accept()
        if self.popup:
            if self in WINDOWS:
                WINDOWS.remove(self)
            self.deleteLater()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8765/')
    parser.add_argument('--profile-dir', type=Path)
    args = parser.parse_args()
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ProjectNova.Controller')
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Nova Controller')
    app.setOrganizationName('Project Nova')
    app.setWindowIcon(nova_icon())
    try:
        base = controller_profile_dir(args.profile_dir)
    except OSError as error:
        QMessageBox.critical(None, 'Nova Chat could not open its saved profile', str(error))
        return 1
    settings = QSettings(str(base / 'window.ini'), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    profile = QWebEngineProfile('NovaController', app)
    profile.setPersistentStoragePath(str(base / 'storage'))
    profile.setCachePath(str(base / 'cache'))
    def download(request):
        path, _ = QFileDialog.getSaveFileName(None, 'Save Nova export', request.downloadFileName())
        if path:
            request.setDownloadDirectory(str(Path(path).parent))
            request.setDownloadFileName(Path(path).name)
            request.accept()
        else:
            request.cancel()
    profile.downloadRequested.connect(download)
    window = Controller(profile, settings)
    WINDOWS.append(window)
    window.view.setUrl(QUrl(args.url))
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
