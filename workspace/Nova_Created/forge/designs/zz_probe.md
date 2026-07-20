# zz_probe — temporary verification tool
## The gap
Verifying that a tool dropped into Nova_Created/forge/tools is discovered live, with no
restart, now that the forge writes to her creations folder instead of her body.
## Behaviour
Returns a fixed string so the round-trip is unambiguous.
## Test
tests/zz_probe.py asserts the exact return value.