# -*- mode: python ; coding: utf-8 -*-
# Nova stub spec
# Builds a tiny launcher exe (~5 MB) with NO bundled nova packages.
# The real packages live in the workspace folder and are loaded at runtime
# by the system Python -- so code changes take effect on the next launch
# with zero rebuild required.

a = Analysis(
    [os.path.join(SPECPATH, 'nova_stub.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'fastapi', 'uvicorn', 'httpx', 'discord', 'PyQt6',
        'apscheduler', 'requests', 'websocket', 'anyio',
        'numpy', 'PIL', 'pyautogui',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='Nova',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
