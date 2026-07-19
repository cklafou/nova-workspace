import sys
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
print(dir(store))
