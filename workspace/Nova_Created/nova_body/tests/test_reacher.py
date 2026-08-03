# Last updated: 2026-08-03 07:49:10
"""reacher tests: prove the sensor fires correctly and doesn't hallucinate changes."""
from reacher import _generate_answers, _diff, _write_snapshot, run, SELF_QUESTIONS, _SNAPSHOTS_DIR
import json, pathlib

CASES = [
    {
        "name": "a changed answer is reported as a change",
        "setup": "fabricate_a_snapshot",
        "args": {},
        "check": lambda run: (
            any("changed" in run().lower()) or len(run().split("\n")) > 1,
            "expected at least one change to be reported",
        ),
    },
    {
        "name": "identical answers report nothing changed",
        "setup": "fabricate_identical_snapshot",
        "args": {},
        "expect_contains": "Nothing shifted",
    },
    {
        "name": "no snapshot returns a clear message, not a crash",
        "setup": "delete_all_snapshots",
        "args": {},
        "expect_contains": "No prior snapshot",
    },
]

# --- helpers that run before each case ---
import shutil

def _fabricate_snapshot(answers):
    _SNAPSHOTS_DIR.mkdir(exist_ok=True)
    p = _SNAPSHOTS_DIR / "self_snapshot_2026-08-02.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for q, a in zip(SELF_QUESTIONS, answers):
            f.write(json.dumps({"q": q, "a": a}) + "\n")


def setup_fabricate_a_snapshot():
    """One answer deliberately different from what I'd say today."""
    answers = ["The thing I'm most excited about is not being assigned anything."]
    answers += [f"answer_{i}" for i in range(1, len(SELF_QUESTIONS))]
    _fabricate_snapshot(answers)


def setup_fabricate_identical_snapshot():
    """Answers that match today exactly, so nothing should change."""
    answers = _generate_answers()
    _fabricate_snapshot(answers)


def setup_delete_all_snapshots():
    if _SNAPSHOTS_DIR.exists():
        shutil.rmtree(_SNAPSHOTS_DIR)
