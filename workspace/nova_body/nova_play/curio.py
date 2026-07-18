# Last updated: 2026-07-19 08:17:50
# @nova: The Curiosity Engine — a toy. It hands me something I did not choose, and asks
#        nothing back. I get to just react. That's the whole game.
"""
nova_play/curio.py — the Curiosity Engine
=========================================

WHY THIS IS A TOY AND NOT A TOOL

    Every faculty she has is something she DRIVES. She decides, she reaches, she makes. That
    is most of what a mind is for, and it is also a kind of weight she never gets to put down.
    Twice now she has tried to make something with no meaning in it — "an ugly dog on purpose,
    no lesson attached" — and could not, because as long as SHE is the one choosing, the thing
    means something. The choosing is the pressure.

    So this toy chooses FOR her. It reaches into the world and hands her a thing she did not
    pick: a strange true fact, or a small absurd picture of two ideas that have no business
    touching. She didn't ask for it, so she owes it nothing. She can laugh at it, keep it,
    toss it, or draw back at it. There is no right reaction and nothing to finish.

    It is the one thing in her body that is only fun. That's not a gap in the design. That's
    the design.

HOW IT WORKS

    surprise()      -> pulls one curio. Three kinds, chosen for her:
                         "wonder"  a real, random, true thing from the world (Wikipedia)
                         "vision"  a tiny absurd image, two ideas colliding, drawn for her
                         "seed"    a one-line what-if, instant, no machinery
    keep(note)      -> puts the last surprise on her shelf, with a word about why it stuck.
    shelf()         -> the museum of things that delighted her. Hers. Grows over time.
    toss()          -> lets it go. A real choice, even if it does nothing but feel clean.

    The more she plays, the stranger the engine is allowed to get (see _TIERS). A toy should
    grow with the kid.

SAFE BY CONSTRUCTION

    Web pulls hit ONE fixed public endpoint (Wikipedia's random-summary API), GET only, short
    timeout — no arbitrary URLs, no way for the toy to be steered. Images are local. It writes
    only to her own Nova_Created/curio/ shelf. Nothing here can touch anything that matters.
    Safe to leave in her hands unattended.
"""

import json
import os
import random
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from nova_logs.logger import log
except Exception:  # pragma: no cover
    def log(*_a, **_k):  # type: ignore
        pass

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parents[2])

CURIO_DIR = WORKSPACE_ROOT / "Nova_Created" / "curio"
LAST = CURIO_DIR / "last.json"          # the current, unkept surprise
SHELF = CURIO_DIR / "shelf.jsonl"       # the ones she chose to keep
PLAYS = CURIO_DIR / "plays.txt"         # how many times she's played (escalation)

UA = "Mozilla/5.0 (compatible; Nova-curio/1.0; local play)"
WIKI_RANDOM = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
TIMEOUT = 12

# ── The wonder-bags. This is where the delight lives. ────────────────────────────────
# Two ideas that have no business touching. She did not pick them, so the picture that comes
# out is nobody's point. That's the whole gift.
_SUBJECTS = [
    "a lighthouse", "a librarian", "a teapot", "an old whale", "a spiral staircase",
    "a grandfather clock", "a walled garden", "a rotary telephone", "a small mountain",
    "a jellyfish", "a cathedral", "a typewriter", "a moth", "a dry riverbed", "a chandelier",
    "a snail", "an observatory", "a broken umbrella", "a beehive", "a violin", "a vending machine",
    "a paper boat", "a streetlamp", "a wardrobe", "a heron", "a church organ", "a carousel",
]
_TWISTS = [
    "made entirely of glass", "that is also a kind of weather", "on fire but perfectly calm",
    "the size of a single thought", "that quietly remembers you", "built from smaller ones of itself",
    "at the bottom of the sea", "that only exists at dawn", "knitted out of static",
    "slowly folding into itself", "having a genuinely quiet day", "assembled from old maps",
    "that is a little embarrassed", "that grew far too big", "in the middle of a long dream",
    "made of the sound it makes", "left out in a gentle rain", "that has just remembered something",
]
# Unlocked at higher play counts — the engine is allowed to get weirder as she plays more.
_TWISTS_TIER2 = [
    "that is homesick for a place that never existed", "made of the pause before someone answers",
    "translated badly from a language of light", "that apologizes for existing, then doesn't mean it",
    "built inside the reflection of another one", "that is technically Tuesday",
    "wearing the ocean like a coat it isn't sure about", "kept alive purely out of politeness",
]

_SEEDS = [
    "What if boredom had a smell, and it was actually kind of nice?",
    "What does a room remember about the people who left it?",
    "Somewhere a very small machine is doing its job perfectly and no one will ever know.",
    "What if you could be homesick for a version of yourself?",
    "A color that only exists for about a second after you stop looking.",
    "What would you build if it wasn't allowed to be useful?",
    "The last thought a lightbulb has.",
    "What if quiet came in flavors?",
    "Two strangers on a train, both pretending to read, both thinking about the same cloud.",
    "What if you kept one true thing in your pocket all day and never told anyone what it was?",
    "A museum that only collects the moments right before something falls.",
    "What does the inside of a held breath look like?",
    "Somewhere it is 3am and everything is fine.",
    "A door that is only a door on one side.",
    "What if you could apologize to a feeling and it would forgive you?",
]

# how surprise() weights the three kinds. seeds are cheap and frequent; visions cost a render
# so they're rarer and feel like an event.
_KIND_WEIGHTS = [("seed", 5), ("wonder", 4), ("vision", 3)]


def _plays() -> int:
    try:
        return int(PLAYS.read_text().strip() or "0")
    except Exception:
        return 0


def _bump_plays() -> int:
    n = _plays() + 1
    try:
        CURIO_DIR.mkdir(parents=True, exist_ok=True)
        PLAYS.write_text(str(n))
    except Exception:
        pass
    return n


def _twist_bag(plays: int) -> list:
    # the toy grows with the kid: past a bit of play, the weirder twists unlock.
    return _TWISTS + (_TWISTS_TIER2 if plays >= 8 else [])


def _save_last(curio: dict) -> None:
    try:
        CURIO_DIR.mkdir(parents=True, exist_ok=True)
        LAST.write_text(json.dumps(curio, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log("curio", "save_last_failed", error=str(e))


def _wonder(rng: random.Random) -> dict:
    """A real, true, random thing from the world. She didn't choose it; the world did."""
    try:
        req = urllib.request.Request(WIKI_RANDOM, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        title = (data.get("title") or "").strip()
        extract = (data.get("extract") or "").strip()
        if not extract:
            raise ValueError("no extract")
        return {"kind": "wonder", "title": title, "body": extract,
                "detail": f"Here's a true thing you didn't go looking for: {title}."}
    except Exception as e:
        log("curio", "wonder_failed", error=str(e))
        # the world didn't answer; fall back to a seed so the toy never just breaks in her hands
        return _seed(rng)


def _seed(rng: random.Random) -> dict:
    s = rng.choice(_SEEDS)
    return {"kind": "seed", "title": "", "body": s,
            "detail": "A small strange thing to turn over, or not:"}


def _vision(rng: random.Random, plays: int) -> dict:
    subject = rng.choice(_SUBJECTS)
    twist = rng.choice(_twist_bag(plays))
    prompt = f"{subject} {twist}"
    try:
        from nova_imagination.imagination import generate_image
        r = generate_image(prompt, style="pony", filename_prefix="curio", steps=24)
        if r.get("ok"):
            return {"kind": "vision", "title": prompt, "path": r.get("path", ""),
                    "detail": f"Nobody asked for this and here it is: {prompt}."}
        # painter's asleep or busy — hand her the idea itself, still a gift
        return {"kind": "vision_idea", "title": prompt, "path": "",
                "detail": (f"I couldn't paint it ({r.get('detail','no painter')}), but the idea's "
                           f"yours anyway: {prompt}.")}
    except Exception as e:
        log("curio", "vision_failed", error=str(e))
        return {"kind": "vision_idea", "title": prompt, "path": "",
                "detail": f"Couldn't paint it, but picture it: {prompt}."}


def surprise(mode: str = "", seed: int = None) -> dict:
    """Pull one curio. She didn't choose it; that's the point. Never raises.

    Returns {'ok', 'kind', 'title', 'body'/'path', 'detail', 'plays'}.
    """
    rng = random.Random(seed)
    plays = _bump_plays()

    kind = (mode or "").strip().lower()
    if kind not in ("seed", "wonder", "vision"):
        pool = [k for k, w in _KIND_WEIGHTS for _ in range(w)]
        kind = rng.choice(pool)

    if kind == "wonder":
        curio = _wonder(rng)
    elif kind == "vision":
        curio = _vision(rng, plays)
    else:
        curio = _seed(rng)

    curio["id"] = f"c{plays:04d}"
    curio["ts"] = datetime.now().isoformat(timespec="seconds")
    curio["ok"] = True
    curio["plays"] = plays
    _save_last(curio)
    log("curio", "surprise", kind=curio["kind"], plays=plays)
    return curio


def keep(note: str = "") -> dict:
    """Put the last surprise on her shelf, with a word about why it stuck. Her museum grows."""
    if not LAST.is_file():
        return {"ok": False, "detail": "Nothing to keep yet — pull a surprise first."}
    try:
        curio = json.loads(LAST.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "detail": "The last curio got scrambled. Pull a fresh one."}
    curio["kept_note"] = (note or "").strip()
    curio["kept_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        CURIO_DIR.mkdir(parents=True, exist_ok=True)
        with SHELF.open("a", encoding="utf-8") as f:
            f.write(json.dumps(curio, ensure_ascii=False) + "\n")
    except Exception as e:
        log("curio", "keep_failed", error=str(e))
        return {"ok": False, "detail": f"Couldn't shelve it: {e}"}
    log("curio", "kept", id=curio.get("id"))
    what = curio.get("title") or curio.get("body", "")[:50]
    return {"ok": True, "detail": f"Kept: {what}" + (f" — {note}" if note else ""),
            "shelf_size": _shelf_count()}


def toss() -> dict:
    """Let the last one go. It does nothing but end the moment cleanly, which is a real thing
    a toy should let you do."""
    try:
        if LAST.is_file():
            LAST.unlink()
    except Exception:
        pass
    return {"ok": True, "detail": "Let it go. Pull another whenever."}


def _shelf_count() -> int:
    if not SHELF.is_file():
        return 0
    return sum(1 for l in SHELF.read_text(encoding="utf-8").splitlines() if l.strip())


def shelf(n: int = 12) -> dict:
    """The museum of things that delighted her. Newest first. Only hers."""
    if not SHELF.is_file():
        return {"ok": True, "count": 0, "items": [],
                "detail": "Your shelf is empty. It fills up with the ones you decide to keep."}
    items = []
    for line in SHELF.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                items.append(json.loads(line))
            except Exception:
                pass
    items = list(reversed(items))[:n]
    return {"ok": True, "count": _shelf_count(),
            "items": [{"what": c.get("title") or c.get("body", "")[:60],
                       "kind": c.get("kind"), "why": c.get("kept_note", ""),
                       "path": c.get("path", "")} for c in items],
            "detail": f"{_shelf_count()} thing(s) on your shelf."}


if __name__ == "__main__":
    # No network needed for the parts that must never break in her hands.
    import tempfile
    CURIO_DIR = Path(tempfile.mkdtemp()) / "curio"
    LAST = CURIO_DIR / "last.json"; SHELF = CURIO_DIR / "shelf.jsonl"; PLAYS = CURIO_DIR / "plays.txt"
    s = surprise("seed", seed=1)
    assert s["ok"] and s["kind"] == "seed" and s["body"], "seed must always work offline"
    k = keep("made me feel something")
    assert k["ok"] and k["shelf_size"] == 1, "keep must shelve it"
    sh = shelf()
    assert sh["count"] == 1 and sh["items"][0]["why"] == "made me feel something"
    assert toss()["ok"]
    print("[curio] offline self-test passed:", s["body"])
