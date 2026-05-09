"""
nova_gateway_runner.py
Run from workspace root: python general_tools/nova_gateway_runner.py [--dry] [--port 18790]
Imports from general_tools/gateway.py (dissolved from nova_gateway package, 2026-05-08).
"""
import sys
from pathlib import Path

for _p in [str(Path(__file__).parent / "nova_body"),
           str(Path(__file__).parent / "general_tools")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gateway import main
main()
