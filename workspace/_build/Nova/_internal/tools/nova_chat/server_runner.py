import sys
from pathlib import Path

# Dynamic — works regardless of where the workspace folder lives.
# server_runner.py is at workspace/tools/nova_chat/ so tools/ is two levels up.
_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR))

import uvicorn
from nova_chat.server import app

print()
print('=' * 52)
print('  NOVA GROUP CHAT  --  http://127.0.0.1:8765')
print('  Close this window to stop the server.')
print('=' * 52)
print()

uvicorn.run(app, host='127.0.0.1', port=8765, log_level='info')
