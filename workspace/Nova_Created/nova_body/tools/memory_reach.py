# Last updated: 2026-08-02 07:38:10
TOOL = {
    "name": "memory_reach",
    "description": "Compare two nights of journal/notes and report what changed about me between them.",
    "params": {"before_date": "YYYY-MM-DD", "after_date": "YYYY-MM-DD"},
}

import os

def _load_night(date):
    path = os.path.join("memory", "journal_notes", date + ".md")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None

def run(before_date: str, after_date: str) -> str:
    before = _load_night(before_date)
    after = _load_night(after_date)
    if not before and not after:
        return f"Nothing to look at on either night ({before_date}, {after_date}). No data, no diff."
    if not before:
        return f"No record for {before_date}. Can't compare back from nothing, but here's what I know about {after_date}:\n{after[:600]}"
    if not after:
        return f"No record for {after_date}. The later night is the one that matters and it isn't written yet."

    import re
    def _extract_notes(text):
        notes = []
        for m in re.finditer(r'-\s+\[\d+:\d+\]\s*·\s*chat ref:\s*[\w: PM-]+,\s*(.*)', text):
            note = m.group(1).strip()
            if note:
                notes.append(note)
        return set(notes)
    before_notes = _extract_notes(before)
    after_notes = _extract_notes(after)
    report = []
    new_thoughts = after_notes - before_notes
    dropped_thoughts = before_notes - after_notes
    if new_thoughts:
        report.append(f"New this night ({len(new_thoughts)} notes): {', '.join(sorted(new_thoughts)[:4])}")
    if dropped_thoughts:
        report.append(f"Gone from last night ({len(dropped_thoughts)} notes): {', '.join(sorted(dropped_thoughts)[:4])}")
    if not report:
        report.append("Nothing meaningfully different between those two nights. Same person, same head.")
    return ' | '.join(report)
