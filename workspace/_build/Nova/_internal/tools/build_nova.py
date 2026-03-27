"""
build_nova.py
==============
Build Nova.exe — the unified Project Nova desktop app.

Bundles NovaLauncher.py into a single Windows executable.
The resulting Nova.exe starts nova_chat + nova_gateway and opens the UI
in a native desktop window (no browser, no terminal visible).

Requirements:
  pip install pyinstaller pywebview

Run from workspace/tools/:
  python build_nova.py

Output: workspace/_build/Nova/Nova.exe
"""

import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_WS    = _TOOLS.parent
_BUILD = _WS / "_build"

def main():
    print("Building Nova.exe...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",             # folder bundle: faster startup, easier to inspect
        "--windowed",           # no console window (errors go to logs/nova_launcher.log)
        "--name", "Nova",
        "--distpath", str(_BUILD),
        "--workpath", str(_BUILD / "build_nova"),
        "--specpath", str(_BUILD),
        "--add-data", f"{_TOOLS};tools",   # bundle entire tools/ dir
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "fastapi",
        "--hidden-import", "webview",
        "--hidden-import", "discord",
        "--hidden-import", "apscheduler",
        str(_TOOLS / "NovaLauncher.py"),
    ]

    result = subprocess.run(cmd, cwd=str(_TOOLS))
    if result.returncode == 0:
        exe_path = _BUILD / "Nova" / "Nova.exe"
        print()
        print("=" * 52)
        print(f"  SUCCESS: {exe_path}")
        print("  Run Nova.exe to launch the full Nova stack.")
        print("  Errors log to: Nova/logs/nova_launcher.log")
        print("=" * 52)
    else:
        print("Build failed. Check output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
