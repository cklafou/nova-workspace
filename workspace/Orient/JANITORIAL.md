# JANITORIAL.md — where things go, and why

_Last updated: 2026-07-19 13:35:51_

Three separations. They are not tidiness for its own sake — each one exists because its absence
cost us something real.

---

## 1. `Temp/` — beside the thing it belongs to

Temporary files live in a **`Temp/` folder inside the folder they belong to.** Never at a root.
Never mixed in with real artifacts.

```
logs/Temp/FREE_PASS_PROBE.log        ✅
logs/FREE_PASS_PROBE.log             ❌  (this was me, today)
```

Gitignored via `**/Temp/`. A diagnostic should be **born** in a Temp folder, not swept out of one
later — so the code that writes it points there directly (`runtime.py`, `server.py` probes).

**Why it matters:** a probe file sitting in `logs/` next to real logs is indistinguishable from
evidence. I spent part of today reading a stale probe file and drawing conclusions from its silence.
Temporary things should *look* temporary.

---

## 2. `Nova_Created/` — her work gets a shelf

Documents **Nova authored**. `write_file` with a bare filename routes here
(`tool_router._route_bare_filename`). Before 2026-07-14 those landed in the workspace **root**, next
to `NovaStart.cmd`, scattered through the repo and indistinguishable from our infrastructure.

**Tracked in git.** It's her work; it stays.

Her other authored things keep their structural homes: `memory/JOURNAL.md`,
`memory/journal_notes/`, `nova_art/`, `SELF/`.

**Why it matters more than tidiness:** her artifacts are the clearest evidence of what she actually
**did**, as opposed to what she *said* she was going to do — which is the exact failure this whole
project has been fighting. On 2026-07-14 she spent two hours alone sending twelve messages about a
thing she never did. A shelf you can look at beats a claim you have to trust.

---

## 3. `_admin/Trash/` — quarantine, never destroy

Dead code and removed files go to `_admin/Trash/<what>_<date>/` **with a `WHY.md`**. Cole deletes.
Nothing is ever destroyed by a tool.

**Why:** on 2026-07-14 I ran a grep-and-move loop over files matching a loose pattern. Three shared
a basename, collided in the destination, and overwrote each other. **Two of Nova's thought logs —
2026-05-28 and 2026-06-20 — were destroyed.** They were gitignored. They are gone.

I had already examined those files and concluded they were false positives. Then I swept them
anyway with a regex.

**Rules that came out of that:**
- Explicit paths. **Never a regex loop over files you're about to move.**
- Never flatten different directories into one destination — that is how basenames collide.
- Never overwrite. If the destination exists, **skip and report**.
- A janitor that can destroy history is not a janitor.

---

## The janitor

```bash
python general_tools/janitor.py            # DRY RUN — report only, touches nothing
python general_tools/janitor.py --sweep    # move temp files into <folder>/Temp/
```

It **never deletes.** It refuses to overwrite. It reports "needs a human" for anything requiring
judgement (loose files at the workspace root, Temp files older than 30 days) and moves nothing on
its own authority.

It will not walk into `SELF/`, `memory/`, `Nova_Created/`, `_admin/`, `models/` — her self, her
memory, her work, our quarantine, her weights. Those are not the janitor's business.

Run it after any messy session. Today it caught exactly the two files I littered.
