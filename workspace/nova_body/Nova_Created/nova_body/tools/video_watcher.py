# Last updated: 2026-10-05 21:25:38
# video_watcher - grab several frames across a few seconds so I see motion, not stills
TOOL = {
    "name": "video_watcher",
    "description": "Capture several frames from my own screen across a few seconds so I can describe actual motion instead of one still.",
    "params": {"seconds": "how long to watch", "interval": "seconds between frames"},
}
import time, uuid
from nova_paths import body_path

def run(seconds=6, interval=2):
    from nova_computer.hands import Hands
    from nova_computer.computer import NovaComputer
    pc = NovaComputer(); hands = Hands(pc)
    if seconds < 1 or interval < 1:
        return "ERROR: need at least 1 second and 1s spacing"
    n = max(1, int(seconds // interval) + 1)
    frames = []
    for i in range(n):
        img = hands.look()
        if not img:
            return f"ERROR: could not capture frame {i} - display unreachable"
        p = body_path('logs', 'video_frames', str(uuid.uuid4()) + '.png')
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(img)
        frames.append(str(p))
        if i < n - 1:
            time.sleep(interval)
    return f"Captured {len(frames)} frames across ~{seconds}s: " + "; ".join(frames)