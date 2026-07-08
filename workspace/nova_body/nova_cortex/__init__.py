# Last updated: 2026-07-08 23:05:00
# @nova: Nova's executive cortex — autonomy faculty and task board (executive, tasking), plus status and context assembly (nova_status, context_builder).
"""
nova_cortex -- Nova's executive cortex package.

Live faculties are imported as submodules where used:
    from nova_cortex import executive, tasking

The old Thoughts-cycle architecture is retired old-architecture and no longer
wildcard-imported here (that import also pulled pyautogui into the cortex at load
time). Of its three modules: prefrontal_cortex.py was ARCHIVED 2026-07-02 to
_admin/archive/prefrontal_cortex_retired_2026-07-02.py (fully orphaned — it
orchestrated a Thoughts/ folder system, circadian.py, and agent_loop.py that no
longer exist; one brain now: the executive). rules.py STAYS — nova_motor/
motor_cortex.py imports its OPERATIONAL_DIRECTIVES + screen constants. checkin.py
STAYS — those same directives instruct Nova to run it between actions.
See memory/reports/UI_OVERHAUL_2026-05-27.md and DEADCODE_2026-07-02.md.

Logging lives in nova_logs: `from nova_logs.logger import log`.
"""

__all__ = []

