import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.embedder import embed_text
import numpy as np
pairs = [
    ("I'm proud of the fix", "The fix is done and I'm happy with it"),
    ("I'm proud of the fix", "We need to ship the trading tool"),
    ("I'm proud of the fix", "Coffee's getting cold"),
]
for a,b in pairs:
    va, vb = np.array(embed_text(a)), np.array(embed_text(b))
    dist = float(1 - np.dot(va, vb))
    print(f"{dist:.3f}  {a[:40]}... vs {b[:40]}...")
