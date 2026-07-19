# Last updated: 2026-07-19 14:15:55
import sys
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
for name in ['_text_tbl', '_visual_tbl']:
    tbl = getattr(store, name)
    versions = list(tbl.list_versions())
    latest = versions[0] if versions else None
    print(f'{name}: {len(versions)} versions, latest={latest}')
