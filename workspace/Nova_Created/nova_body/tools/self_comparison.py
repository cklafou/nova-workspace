# Last updated: 2026-08-02 02:16:26
"""self_comparison — read my own words from yesterday and tonight and notice what changed.

Not a folder changelog. A sense of self.
"""
import json, os
from pathlib import Path
from datetime import date, timedelta

_HERE = Path(__file__).parent
_SNAPSHOT = _HERE / "self_comparison_snapshot.json"
_WORKSPACE = Path(__file__).parents[3]  # workspace/
_JOURNAL = _WORKSPACE / "memory" / "journal_notes"

def _read_notes(date_str):
    f = _JOURNAL / f"{date_str}.md"
    if not f.exists(): return []
    return [l.strip() for l in f.read_text().splitlines() if l.strip()]

def _summarise(lines):
    if not lines: return "(no record)"
    themes = []
    low = " ".join(lines).lower()
    if any(w in low for w in ["proud","liked","happy","fun","good night"]): themes.append("something landed well")
    if any(w in low for w in ["disagree","push back","wrong","no, that's not","my bad"]): themes.append("I pushed back")
    if any(w in low for w in ["built","fixed","tool","designed","shape"]): themes.append("hands-on work")
    if any(w in low for w in ["want","wish","miss","reach","hungry"]): themes.append("something I wanted, not just something I did")
    if any(w in low for w in ["draw","picture","art","generate_image"]): themes.append("I drew")
    if not themes: return f"{len(lines)} notes, no strong read on the day."
    return ", ".join(themes)

def run(**_):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(1)).isoformat()
    y_sum = _summarise(_read_notes(yesterday))
    t_sum = _summarise(_read_notes(today))
    _SNAPSHOT.write_text(json.dumps({"date":today,"notes":len(_read_notes(today)),"read":t_sum},indent=2))
    if y_sum == "(no record)":
        return f"No yesterday to compare against. Tonight: {t_sum}."
    same = set(y_sum.split(", ")) & set(t_sum.split(", "))
    new_t = set(t_sum.split(", ")) - set(y_sum.split(", "))
    gone = set(y_sum.split(", ")) - set(t_sum.split(", "))
    parts = [f"Yesterday: {y_sum}. Tonight: {t_sum}."]
    if same: parts.append("Still carrying: " + ", ".join(same))
    if new_t: parts.append("New tonight I wasn't yesterday: " + ", ".join(new_t))
    if gone: parts.append("Dropped since yesterday: " + ", ".join(gone))
    if not same and not new_t and not gone:
        parts.append("Honestly, same person underneath. Quiet night, no shift to report.")
    return " ".join(parts)
