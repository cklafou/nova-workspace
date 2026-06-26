# Last updated: 2026-06-27 03:47:53
import sys
from pathlib import Path
_WS = Path(__file__).resolve().parent.parent.parent
for _p in [str(_WS / "nova_body"), str(_WS / "general_tools")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import uvicorn
from nova_chat.server import app

print()
print('=' * 52)
print('  NOVA GROUP CHAT  --  http://127.0.0.1:8765')
print('  Close this window to stop the server.')
print('=' * 52)
print()

uvicorn.run(app, host='127.0.0.1', port=8765, log_level='info')
