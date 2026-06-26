# Last updated: 2026-06-27 01:43:48
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

# Match the default boot's import surface exactly: server_runner.py adds nova_body +
# general_tools, and launching nova_start.py from the workspace root adds the root as
# script dir. Headless must offer the same three or leaf imports break on a real pluck —
# seen live 2026-06-10: `nova_lancedb` (indexer) and `nova_chat.clients` (model client)
# both unimportable with nova_body alone. Insert in reverse priority: nova_body wins.
_NOVA_BODY = Path(__file__).resolve().parent.parent
_WS = _NOVA_BODY.parent
for _p in (str(_WS), str(_WS / "general_tools"), str(_NOVA_BODY)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
