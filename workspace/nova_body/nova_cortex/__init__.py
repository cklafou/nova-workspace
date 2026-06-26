# Last updated: 2026-06-27 03:47:53
# @nova: Nova's executive cortex — autonomy faculty and task board (executive, tasking), plus status and context assembly (nova_status, context_builder).
"""
nova_cortex -- Nova's executive cortex package.

Live faculties are imported as submodules where used:
    from nova_cortex import executive, tasking

The old Thoughts-cycle modules (rules, prefrontal_cortex, checkin) are retired
old-architecture. They are no longer wildcard-imported here — that import also
pulled pyautogui into the cortex at load time, coupling her whole brain to a
GUI-automation dependency it doesn't use. The files remain on disk
(archive-don't-delete) but are not part of the live cortex.
See memory/reports/UI_OVERHAUL_2026-05-27.md.

Logging lives in nova_logs: `from nova_logs.logger import log`.
"""

__all__ = []

