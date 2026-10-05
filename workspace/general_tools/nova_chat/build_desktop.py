# Last updated: 2026-10-05 18:30:24
"""Build the controller executable without bundling Nova's body, state or models."""
from pathlib import Path
import os
import subprocess
import sys
import PyQt6


def main():
    source = Path(__file__).resolve().parent
    workspace = source.parents[1]
    output = (workspace / '_build' / 'NovaController').resolve()
    if not output.is_relative_to(workspace.resolve()):
        raise RuntimeError('Build output must stay inside the Nova workspace')
    qt_bin = Path(PyQt6.__file__).parent / 'Qt6' / 'bin'
    # Package the Qt runtime, not unrelated DLLs exposed by an application on PATH.
    # Qt 6.11 also needs a newer VC runtime than the Python 3.12 installation bundles.
    env = os.environ.copy()
    windows = Path(env.get('WINDIR', r'C:\Windows'))
    env['PATH'] = os.pathsep.join(map(str, [qt_bin, windows / 'System32', windows, Path(sys.executable).parent]))
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--windowed', '--onedir', '--clean', '--noconfirm',
        '--name', 'NovaController',
        '--add-binary', str(qt_bin / 'VCRUNTIME140.dll') + os.pathsep + '.',
        '--add-binary', str(qt_bin / 'VCRUNTIME140_1.dll') + os.pathsep + '.',
        '--distpath', str(workspace / '_build'),
        '--workpath', str(workspace / '_build' / 'controller-build'),
        '--specpath', str(workspace / '_build'),
        str(source / 'desktop.py'),
    ], check=True, env=env)


if __name__ == '__main__':
    main()
