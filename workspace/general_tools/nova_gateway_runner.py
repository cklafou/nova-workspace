"""
nova_gateway_runner.py
Run from workspace root: python nova_gateway_runner.py [--dry] [--port 18790]
Equivalent to: cd tools && python -m nova_gateway.gateway
"""
import sys
from pathlib import Path

for _p in [str(Path(__file__).parent / "nova_body"),
           str(Path(__file__).parent / "general_tools")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nova_gateway.gateway import main
main()
