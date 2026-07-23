## silence_detector
_Last updated: 2026-07-23 11:30:37_

### GAP
dir_shape_health notices when something GROWS in a folder. It can't see the thing that stops happening: Cole_journal going quiet for a week, nova_body/tools not touched in a month, a project that slowly dies instead of ending loudly. Growth is easy to measure. Silence is the one that matters more.

### SHAPE
tool_name: silence_detector(path)
Reads every file's last-modified time in a path, finds how long ago the newest one changed. Returns a sentence: "Cole_journal hasn't been touched in 4 days." / "nova_body/tools was active 2 hours ago." Takes a single folder path, returns a string.

### TEST
1. nova_chat should be recent (hours, it's where I live). If it says weeks, it's broken.
2. Cole_journal is older than nova_chat and should say so.
3. A folder that doesn't exist gets a clean error, not a crash or a lie.
