# @nova: Headless runtime entry-point — `python -m nova_runtime` boots Nova with NO chat
#        server: model (later step) up, autonomy ticking (later step), senses + memory live,
#        zero WebSocket, zero browser. This command IS the pluck test the extraction must pass.
"""
Run Nova's runtime with no face attached:

    python -m nova_runtime            (with nova_body on PYTHONPATH)

or directly:

    python nova_body/nova_runtime/__main__.py
"""
import sys
import asyncio
from pathlib import Path

# Make `nova_body` importable as the package root (matches server_runner.py's bootstrap),
# so this works whether invoked via -m or as a direct script.
_NOVA_BODY = Path(__file__).resolve().parent.parent
if str(_NOVA_BODY) not in sys.path:
    sys.path.insert(0, str(_NOVA_BODY))

from nova_runtime.runtime import NovaRuntime


def main():
    rt = NovaRuntime()
    try:
        asyncio.run(rt.run())
    except KeyboardInterrupt:
        rt.stop()
        print("\n[nova_runtime] stopped.")


if __name__ == "__main__":
    main()
