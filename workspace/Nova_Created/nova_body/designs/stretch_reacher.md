# Stretch Reacher
_Last updated: 2026-07-23 15:40:28_

GAP: The watcher decides Cole needs a nudge, but nobody delivers it. The stretch map is a file nobody opens.

SHAPE:
  nova_body tool, body/ side (stdlib + nova_body only).
  run(runtime) -> str: calls stretch_watcher.check(runtime), returns the nudge or "clean".
  Sits in a runtime heartbeat every 10 minutes so it reaches him first instead of waiting in a drawer.

TEST: normal case fires a nudge, empty-log case returns clean without touching Cole.
