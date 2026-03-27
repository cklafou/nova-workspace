"""
nova_memory -- Nova Memory Package
Import directly:
    try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log
    from nova_memory.journal import append
    from nova_memory.state import NovaState
    from nova_memory.status import update_status
    from nova_memory.log_reader import summarize_today
"""
# No wildcard imports -- state.py imports from nova_advisor and nova_perception
# which causes circular imports if loaded here at package init time.

