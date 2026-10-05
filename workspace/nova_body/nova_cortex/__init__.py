# @nova: Expose Nova's executive faculties, task board, runtime settings and body-owned context assembly.
# Last updated: 2026-10-05 21:26:09
"""
nova_cortex -- Nova's executive cortex package.

Live faculties are imported as submodules where used:
    from nova_cortex import executive, tasking

The legacy Thoughts-cycle and gateway-bootstrap helpers are retired. No wildcard
imports run at package initialization. The runtime owns unanswered-message
perception through its transcript; environment.cole_typing supplies the executive's
human-typing gate. Body-owned workspace_context assembles current prompt context.

Logging lives in nova_logs: `from nova_logs.logger import log`.
"""

__all__ = []
