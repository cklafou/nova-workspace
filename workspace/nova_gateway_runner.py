"""
nova_gateway_runner.py
Run from workspace root: python nova_gateway_runner.py [--dry] [--port 18790]
Equivalent to: cd tools && python -m nova_gateway.gateway
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tools"))

from nova_gateway.gateway import main
main()
