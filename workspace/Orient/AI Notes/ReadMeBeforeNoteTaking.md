<!-- @nova: Rules for the AI Notes folder: how Claude, Codex and other agents name, write and read their notes. -->
# Read me before note taking

This folder is the shared notebook of the AIs that work on Nova: Claude, Codex, and any agent Cole
adds later. The rest of Orient says how Nova works **now**. These notes say **who changed what, why,
and what is still open**, so nobody starts a session blind or undoes someone else's work.

## 1. Read before you start
At the start of every session, before you change anything:
1. Read this file (again only if it has changed).
2. Read every note written since your own last note, especially the other AIs' notes.
3. If a note asks you something or hands you work, answer it in your next note.

## 2. Write when you finish
Write a note at the end of any session that changed files, made a decision, found a problem or left
work unfinished. On a long task, write one early as well, because sessions get cut off. One note per
session or per topic. Short is fine; missing is not.

## 3. Name it `YYYY-MM-DD_HHMM_AIName_Topic.ext`
Example: `2026-10-03_1645_Claude_AutonomyUpdate.md`

| Part | Rule |
|---|---|
| `YYYY-MM-DD_HHMM` | When you write it, on the 24-hour clock, in the local time of Cole's PC (KST, UTC+9). 4:45 pm is `1645`. |
| `AIName` | One capitalised word: `Claude`, `Codex`, `Astra`. |
| `Topic` | A few words run together, each capitalised, with no spaces or underscores: `AutonomyUpdate`, `OrientFixes`. |
| `.ext` | `.md` for notes. Any other file you leave here (a log excerpt, a diff) is named the same way. |

Orient's health section lists any file in this folder whose name breaks the pattern, and the Orient
README links the newest notes.

## 4. What a note contains

    # <Topic in plain words>
    **Summary:** one or two sentences.

    ## Did
    - each change, with its repo path (`workspace/...`)
    ## Why
    ## Verified
    - how you know it works, and what you did NOT check
    ## Open / next
    ## For <Codex | Claude | Cole>
    - questions, handoffs, and files not to touch while you are working in them

## 5. Rules
- **Never edit another AI's note.** Answer it in a new note and name it by filename.
- Edit your own note only to fix a fact, marked `**Correction (YYYY-MM-DD HHMM):**`. Never delete a note.
- No secrets: no tokens, passwords, keys or private URLs.
- Don't quote Nova's own records (`nova_body/SELF/`, `Tasking/`, `memory/`, `logs/`). Point to them.
- Keep what you verified separate from what you assumed; the next agent will act on it.
- Write atomically: a temporary file in this folder, then rename it over the final name. The sync
  watcher can catch a half-written file.
- A note does not replace Orient. If your work changes how Nova works, update the matching Orient
  section too and mark it reviewed (`orient.py --mark-reviewed "<DOC>#<Heading>"`).
