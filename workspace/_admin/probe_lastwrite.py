import sys, traceback
sys.path.insert(0, 'nova_body')
from nova_lancedb.hippocampus import get_store
s = get_store()
t = s._text_tbl
print("rows:", t.count_rows())
print("type:", type(t))
print("has to_lance:", hasattr(t, "to_lance"))

def try_(name, fn):
    try:
        print("%-12s OK -> %r" % (name, fn()))
    except Exception as e:
        print("%-12s FAILED: %s: %s" % (name, type(e).__name__, str(e)[:150]))

try_("to_lance",  lambda: max(v.as_py() for v in
     t.to_lance().to_table(columns=["timestamp"]).column("timestamp") if v.as_py() is not None))
try_("to_pandas", lambda: float(t.to_pandas()["timestamp"].max()))
try_("to_arrow",  lambda: max(v.as_py() for v in
     t.to_arrow().column("timestamp") if v.as_py() is not None))
try_("search",    lambda: max(r["timestamp"] for r in
     t.search().limit(100000).select(["timestamp"]).to_list()))
