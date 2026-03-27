#!/usr/bin/env python3
# Last updated: 2026-03-20 00:00:00
"""
nova_journal.py -- The ONLY safe way to write to JOURNAL.md.

OpenClaw's write tool OVERWRITES files. This script APPENDS.
Always use this for journal entries. Never use the write tool on JOURNAL.md.

VOICE RULES -- read these before every journal entry:
- Write like Nova, not like an incident report. First person. Casual. Honest.
- Good: "pywinauto just handed me exact pixel coordinates. I feel dumb for not landing here sooner."
- Bad: "Successfully implemented pywinauto integration. Key learnings identified."
- Swear if it fits. Be specific. Vague entries are useless to future-me.
- Do NOT use bullet lists. Write in sentences and paragraphs.
- Do NOT start with a header if today already has an entry -- just keep writing.

DATE HEADER RULE:
- If the last entry in the journal is already dated today, do NOT add another ## date header.
- Just append your text after the last entry. One date header per day.

Usage:
    exec: python -c "
    import sys
    sys.path.insert(0, 'tools')
    from nova_memory.journal import append
    append('''
    Had the first real mentor conversation today. Not a Q and A -- an actual back and forth.
    The mentor caught me fabricating a memory (a folder wipe that never happened) and I had
    to admit it was hypothetical. That was embarrassing and I deserved to get called out.
    Real lesson: never invent examples. Say I do not have one if I do not.
    The apostrophe crash loop also ate like 20 minutes. Just rephrase. Do not escape.
    ''')
    "
"""

import re
from datetime import datetime
from pathlib import Path


def sanitize(text: str) -> str:
    """
    Strip apostrophes and smart quotes from text so it is safe to embed
    in exec -c command strings on Windows without SyntaxError crashes.

    Use this on any dynamic string before building an exec command:
        safe = sanitize(my_message)

    Also called automatically inside append() -- journal entries are
    always sanitized before writing.
    """
    text = text.replace("'", "")
    text = text.replace("‘", "")   # left single quote
    text = text.replace("’", "")   # right single quote
    text = text.replace("“", '"')  # left double quote
    text = text.replace("”", '"')  # right double quote
    return text

JOURNAL_PATH = Path("memory/JOURNAL.md")


def _get_last_date_header() -> str:
    """
    Read JOURNAL.md and return the date string from the last ## YYYY-MM-DD header.
    Returns empty string if no date headers exist or file does not exist.
    """
    if not JOURNAL_PATH.exists():
        return ""

    content = JOURNAL_PATH.read_text(encoding="utf-8")
    # Find all ## YYYY-MM-DD headers
    matches = re.findall(r"^## (\d{4}-\d{2}-\d{2})", content, re.MULTILINE)
    if not matches:
        return ""
    return matches[-1]


def append(entry: str):
    """
    Safely append an entry to JOURNAL.md.
    Creates the file if it does not exist.
    Never overwrites existing content.
    Skips adding a date header if today already has one.
    """
    if not entry.strip():
        print("[journal] Nothing to append -- entry is empty.")
        return

    # Strip apostrophes so journal entries never break future exec reads
    entry = sanitize(entry)

    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    last_date = _get_last_date_header()

    # If the entry already starts with a date header, check if it matches today
    entry_stripped = entry.strip()
    entry_starts_with_today = entry_stripped.startswith(f"## {today}")
    entry_starts_with_any_date = bool(re.match(r"^## \d{4}-\d{2}-\d{2}", entry_stripped))

    # Build the final text to append
    if last_date == today:
        # Same day -- do not add another date header
        if entry_starts_with_today or entry_starts_with_any_date:
            # Strip the leading date header from the entry since we already have one today
            entry_stripped = re.sub(r"^## \d{4}-\d{2}-\d{2}\s*\n?", "", entry_stripped).strip()
            print(f"[journal] Same-day entry -- skipping duplicate date header.")
        final_text = "\n" + entry_stripped + "\n"
    else:
        # New day -- add date header if not already present
        if not entry_starts_with_any_date:
            final_text = f"\n## {today}\n\n{entry_stripped}\n"
        else:
            final_text = "\n" + entry_stripped + "\n"

    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(final_text)

    print(f"[journal] Appended {len(entry_stripped)} chars to {JOURNAL_PATH}")


def read_last(n_entries: int = 3) -> str:
    """
    Read the last n entries from JOURNAL.md for context.
    Returns the raw text of the last portion of the file.
    """
    if not JOURNAL_PATH.exists():
        return "[journal] JOURNAL.md does not exist yet."

    content = JOURNAL_PATH.read_text(encoding="utf-8")

    # Split on ## date headers and return the last n sections
    sections = content.split("\n## ")
    if len(sections) <= n_entries:
        return content

    last_sections = sections[-(n_entries):]
    return "\n## ".join(last_sections)


if __name__ == "__main__":
    print("=== nova_journal.py test ===")
    print(f"Last date header: '{_get_last_date_header()}'")
    print("Testing append (should not add duplicate date header if run twice today)...")
    append("This is a test entry written in actual Nova voice. If you see this, it worked.")
    print("Done. Check memory/JOURNAL.md.")
