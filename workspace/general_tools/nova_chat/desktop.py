# Last updated: 2026-10-03 10:59:53
"""Nova desktop face: native windows, menus, tray and persistent renderer profile.

Run with --url for an isolated UI preview. NovaStart owns the runtime processes;
this module never imports Nova's body or starts inference.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QUrl, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QSystemTrayIcon
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView


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
                self.restoreGeometry(geometry)
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
            self.geometry_timer = QTimer(self)
            self.geometry_timer.setInterval(1500)
            self.geometry_timer.timeout.connect(self.save_window)
            self.geometry_timer.start()

    def loaded(self, ok):
        if ok:
            self.statusBar().hide()
        else:
            self.statusBar().showMessage('Nova’s interface is unavailable. Start Nova or use View → Reload to reconnect.')

    def save_window(self):
        if not self.popup and not self.isMinimized():
            self.settings.setValue('geometry', self.saveGeometry())
            self.settings.sync()

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
    base = args.profile_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ProjectNova' / 'Controller'
    base.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(base / 'window.ini'), QSettings.Format.IniFormat)
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
