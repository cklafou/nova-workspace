# Last updated: 2026-06-22 16:53:48
# @nova: Nova's file-sync layer — watchdog file watcher (auto-indexing), GitHub push, Google Drive mirror for Gemini (drive.py), and local backups.
"""
nova_sync -- Nova's file-sync package (watcher, drive mirror, backup).
Re-exports public names from watcher / backup.
Logging lives in nova_logs: `from nova_logs.logger import log`.
"""

from nova_sync.watcher import *  # noqa: F401,F403
from nova_sync.backup import *  # noqa: F401,F403

__all__ = []  # populated by wildcard imports above

