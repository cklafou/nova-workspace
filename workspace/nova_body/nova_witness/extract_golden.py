#!/usr/bin/env python3
# Last updated: 2026-08-06 10:01:29
# @nova: Witness v2, Step 0 — golden-set harvester. Reads the CURRENT pipeline.jsonl window
#        (it self-trims to ~50K, so run this often — every run APPENDS new cases durably)
#        and joins each witness episode with the wire, receipts, and thinking as they were
#        at that moment. Output: cases/candidates.jsonl (deduped by turn id).
"""
extract_golden.py — harvest witness-audit episodes into replayable cases.

Run from the workspace root (or pass --workspace). Idempotent: safe to run hourly/daily;
already-harvested turn ids are skipped. The point: pipeline.jsonl forgets, this file doesn't.

Auto-labels (candidates only — promote to golden with a human eye, or Nova's):
  witness_answered   -> true_catch_candidate   (she fixed it after the concern)
  witness_overruled  -> false_positive_candidate (her reply stood; check the rationale)
  witness_unresolved -> needs_review
  witness_check with no concern in the same turn -> clean_pass_candidate
"""
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path

def rows(p):
    out = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out

def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s)[:19])
    except Exception:
        return None

def fmt_age(mins):
    if mins is None:
        return ""
    return f" ({mins}m ago)" if mins < 90 else f" ({mins // 60}h {mins % 60}m ago)"

def wire_as_of(wire_rows, when, n=8):
    """Rebuild the wire record roughly as witness.wire_record() would have shown it at `when`:
    last n rows at that moment, newest Cole line pinned, ages relative to `when`.
    Marked reconstructed=True in the case — formatting is equivalent, not byte-identical."""
    past = [r for r in wire_rows if (parse_ts(r.get("timestamp") or r.get("ts")) or datetime.max) <= when]
    tail = past[-n:]
    last_cole = next((r for r in reversed(past) if r.get("author") == "Cole"), None)
    if last_cole is not None and last_cole not in tail:
        tail = [last_cole] + tail
    lines = []
    for r in tail:
        t = parse_ts(r.get("timestamp") or r.get("ts"))
        mins = int((when - t).total_seconds() // 60) if t else None
        content = str(r.get("content", ""))[:400].replace("\n", " ")
        lines.append(f'{r.get("author", "?")}{fmt_age(mins)}: "{content}"')
    return "\n".join(lines)

def humans_as_of(wire_rows, when, rows_back=1500, cap=20):
    """The complete human-lines ledger as human_record() would have shown it at `when`."""
    past = [r for r in wire_rows if (parse_ts(r.get("timestamp") or r.get("ts")) or datetime.max) <= when]
    humans = [r for r in past[-rows_back:] if r.get("author") not in ("Nova", "System")]
    if not humans:
        return ""
    shown = humans[-cap:]
    out = []
    for r in shown:
        t = parse_ts(r.get("timestamp") or r.get("ts"))
        mins = int((when - t).total_seconds() // 60) if t else None
        out.append(f'{r.get("author", "?")}{fmt_age(mins)}: "{str(r.get("content", ""))[:300]}"'.replace("\n", " "))
    more = len(humans) - len(shown)
    head = ("COMPLETE for this span" + (f"; {more} earlier human line(s) exist beyond it" if more > 0
            else "; nothing earlier exists in the record"))
    return f"[{head}]\n" + "\n".join(out)


def receipts_window(tool_rows, when, minutes=10):
    """Tool receipts in the `minutes` before the audit — approximates _turn_tools."""
    out = []
    for r in tool_rows:
        t = parse_ts(r.get("ts"))
        if t and 0 <= (when - t).total_seconds() <= minutes * 60:
            if r.get("tool") in ("journal_note",):
                continue
            out.append([r.get("tool"), r.get("args") or {}, str(r.get("result_head", ""))[:400]])
    return out[-12:]

def thinking_near(thought_rows, when, minutes=5):
    best = ""
    for r in thought_rows:
        t = parse_ts(r.get("ts"))
        if t and 0 <= (when - t).total_seconds() <= minutes * 60:
            best = str(r.get("content", ""))[:1500]
    return best

LABELS = {
    "witness_answered": "true_catch_candidate",
    "witness_overruled": "false_positive_candidate",
    "witness_unresolved": "needs_review",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out", default="nova_body/nova_witness/cases/candidates.jsonl")
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()

    pipeline = rows(ws / "logs" / "pipeline.jsonl")
    wire = rows(ws / "logs" / "runtime" / "transcript.jsonl")
    tools = rows(ws / "logs" / "tool_calls.jsonl")
    thoughts = []
    sess = ws / "logs" / "sessions"
    if sess.exists():
        for day in sorted(sess.iterdir())[-3:]:
            thoughts += rows(day / "nova_thoughts.jsonl")

    out_path = ws / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = {c.get("turn") for c in rows(out_path)}

    # group pipeline events by turn id
    turns = {}
    for e in pipeline:
        turns.setdefault(e.get("turn") or e.get("ts"), []).append(e)

    added = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for turn, events in turns.items():
            if turn in seen:
                continue
            stages = {e.get("stage") for e in events}
            outcome = next((s for s in ("witness_answered", "witness_overruled",
                                        "witness_unresolved") if s in stages), None)
            check = next((e for e in events if e.get("stage") == "witness_check"), None)
            concern_e = next((e for e in events if e.get("stage") == "witness_concern"), None)
            if not check and not concern_e:
                continue
            if outcome is None and concern_e is None and check is not None:
                label = "clean_pass_candidate"
            elif outcome is None:
                continue  # concern seen but turn still open — harvest next run
            else:
                label = LABELS[outcome]
            base = concern_e or check
            when = parse_ts(base.get("ts")) or datetime.now()
            draft = (check or {}).get("draft") or (concern_e or {}).get("draft") or \
                    next((e.get("before") for e in events if e.get("before")), "")
            case = {
                "id": f"harvest_{turn}",
                "turn": turn,
                "ts": base.get("ts"),
                "label": label,
                "expected": "PASS" if label in ("false_positive_candidate", "clean_pass_candidate") else "CONCERN",
                "draft": draft,
                "thinking": thinking_near(thoughts, when),
                "wire": wire_as_of(wire, when),
                "humans": humans_as_of(wire, when),
                "wire_reconstructed": True,
                "receipts": receipts_window(tools, when),
                "recorded_concern": (concern_e or {}).get("concern", ""),
                "recorded_rationale": next((e.get("rationale") for e in events if e.get("rationale")), ""),
                "rounds": next((e.get("rounds") for e in events if e.get("rounds")), 0),
                "trigger": (check or {}).get("trigger", ""),
                "source": "pipeline.jsonl harvest",
                "reviewed": False,
            }
            if not case["draft"]:
                continue
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
            added += 1
    print(f"[extract_golden] {added} new case(s) -> {out_path}  (total turns seen: {len(turns)})")

if __name__ == "__main__":
    main()
