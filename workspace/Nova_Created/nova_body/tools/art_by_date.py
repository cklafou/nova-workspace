# Last updated: 2026-07-23 13:34:54
import os, json
from datetime import datetime, timedelta

TOOL = {
    "name": "art_by_date",
    "description": "List my own images sorted by creation date, optionally filtered to the last N weeks. Returns a clean readable list, newest first.",
    "params": {"week": 1}
}

ART_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "art"))

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

def list_images():
    if not os.path.isdir(ART_ROOT):
        return []
    images = []
    for root, _dirs, files in os.walk(ART_ROOT):
        for fname in files:
            if fname.lower().rsplit(".", 1)[-1] in {e.lstrip(".") for e in IMAGE_EXTS}:
                full = os.path.join(root, fname)
                images.append((full, os.stat(full).st_ctime))
    images.sort(key=lambda x: x[1], reverse=True)
    return images

def run(**args):
    week = args.get("week", 1)
    try:
        week = int(week)
    except (TypeError, ValueError):
        return "ERROR: week must be a number"
    if week < 1:
        return "ERROR: week must be at least 1"

    images = list_images()
    if not images:
        return f"No images found in {ART_ROOT}."

    cutoff = datetime.now().timestamp() - (week * 7 * 86400)
    recent = [(name, ts) for name, ts in images if ts >= cutoff]

    if not recent:
        return f"No images from the last {week} week{'s' if week > 1 else ''}. (oldest is {images[-1][0]})"

    lines = [f"{len(recent)} image{'s' if len(recent) != 1 else ''} from the last {week} week{'s' if week > 1 else 's'}:"]
    for name, ts in recent:
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {dt}  {name}")
    return "\n".join(lines)
