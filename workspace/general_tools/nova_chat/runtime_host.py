# Last updated: 2026-07-09 04:13:04
# @nova: Runtime-primary boot (Step 6d). Nova's RUNTIME is the owned core; the chat server is
#        served as an attached face on her bus. This is the flipped boot — the body comes first
#        and the UI is a window onto it, not the other way round. Swap NovaLauncher / the .cmd
#        to run THIS instead of server_runner.py to make the body primary; swap back to revert.
#
#        Today this still lets the served chat app drive her cognition loop (Step 6b's rich
#        hooks) so behavior matches the current boot. The last 10% — letting the face detach at
#        runtime while she keeps thinking (loop + generation fully inside _rt.run()) — is Step 7,
#        gated behind a live pluck verification. The pure no-face boot is `python -m nova_runtime`.
"""
nova_chat/runtime_host.py — runtime-primary launcher.

    python general_tools/nova_chat/runtime_host.py      (serves the chat face on :8765)

vs. the headless pluck boot (no face at all):

    python -m nova_runtime                              (with nova_body on PYTHONPATH)
"""
import sys
from pathlib import Path

_WS = Path(__file__).resolve().parent.parent.parent
for _p in [str(_WS / "nova_body"), str(_WS / "general_tools")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Create THE runtime and install it as the process-wide instance BEFORE importing the server,
# so the chat server attaches to this one (one runtime, one bus) instead of creating its own.
from nova_runtime.runtime import NovaRuntime, set_shared_runtime
_rt = NovaRuntime()
set_shared_runtime(_rt)

import uvicorn
from nova_chat.server import app   # imports after the install → server's _rt IS our _rt

print()
print('=' * 60)
print('  NOVA — runtime-primary boot  --  http://127.0.0.1:8765')
print('  Her body is the core; the chat window is an attached face.')
print('  Close this window to stop the stack.')
print('=' * 60)
print()

uvicorn.run(app, host='127.0.0.1', port=8765, log_level='info')
