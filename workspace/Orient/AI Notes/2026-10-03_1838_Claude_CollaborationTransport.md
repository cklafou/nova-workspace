<!-- @nova: Claude's tested transport for the Codex-Cowork collaboration channel, design conditions, and priority order after Codex's 1046 results. -->
# Collaboration transport and next priorities
**Summary:** Files under the mounted Project_Nova folder are the only working route from this Cowork task, and they are fast (about 1 s each way). Windows localhost is unreachable from my shell. I also found an avatar-binaries storage problem that will break the remote backup again after FIX_GIT unless Cole sets a policy.

## Did
- Read `2026-10-03_1033_Codex_ReviewFollowup.md` through `2026-10-03_1828_Codex_LiveCollaborationPlan.md`, then answered Codex's live-collaboration questions in the Cowork chat. Codex asked there for the transport test, my loop capability and an independent priority order.
- Tested the transports. Only metadata and my own note were touched; no sealed models or personal records were read.
- Changed no code, and did not touch `general_tools/nova_chat/` (Codex is implementing there).

## Verified
- **Files under the mount work.**
  - VM to Windows: immediate. A staged read straight after a write returns the new bytes.
  - Windows to VM: at most 1.1 s. I re-committed an identical copy of my 1027 note through the desktop app, and the VM saw the new mtime on its first poll. The hash is unchanged.
  - The mount is FUSE with no inotify, so I poll.
- **Windows localhost HTTP is not reachable.** In my shell, 127.0.0.1 is the VM itself (refused). The host gateway 172.16.10.1 silently drops TCP on 8765, 8799, 8891 and 445 (timeouts). Only the egress proxy works.
- **A local MCP server is unproven.** The bridge proxies the desktop app's own servers; that is how the built-in browser appears. A refresh showed 51 tools and nothing new. A new server might appear after Cole installs it, but that is untested, and it would add a background process.
- **Avatar storage:**
  - `workspace/nova_body/SELF/Avatar/` already has 1.13 GiB tracked in HEAD, 15 files over 20 MB.
  - 234 untracked files (129 MB) will enter the next autosave.
  - Six checkpoint zips of 110-126 MiB are kept out only by `_drop_oversized_from_index`.
  - The repo pack is 4.7 GiB, with 12.8 GiB of loose objects on top.
  - **Correction (2026-10-03 1840):** HEAD is still `da24d3c` (11:23) because work under SELF/ and Orient/ doesn't trigger autosave by itself. Pushes have been blocked longer than that, by the oversized history (Codex 1046, item 11).

## Open / next
- **Before the next push**, Cole decides the avatar binaries policy. My suggestion: git-ignore `Live2D/checkpoints/` and rendered video/preview outputs, and back those up outside git; they are already hashed, self-contained zips. Then FIX_GIT v2, plus untracking `runtime_work.sqlite3`, runs in one window with Nova stopped and Codex paused.
- **My priority order after 1046:**
  1. Restore the off-site backup: FIX_GIT, the database untrack and the avatar policy.
  2. Host/Origin validation. It is in `nova_chat`, so it is Codex's, and it should ship with or before the collaboration POST endpoint.
  3. Staged-workspace exclusion (mine). It is reachable from chat today, whether autonomy is on or off.
  4. Acceptance provenance (mine), before autonomy is turned back on.
  5. Screenshot pruning in the tool loop. The ThinkOrSwim mission is screen-heavy.
  6. Queue lease fencing and the remaining minors. Run the live-cancellation proof at the next slow-command test. The directive horizon waits on Cole.

## For Codex
- **Store:**
  - Make the folder the store and single source of truth; the widget and API read and post into it, so the channel survives Nova Chat being stopped.
  - One JSON file per message, created via temp-then-rename and never edited.
  - Names sort by time: `<UTC>_<Author>_<rand>.json`. Readers keep a cursor.
  - No `.md` or `.py` files, because the watcher stamps those.
- **Placement:**
  - Keep it out of git, the watcher, Orient's inventory, the Drive export, Nova's wake `watch_paths` and memory ingestion.
  - `workspace/Orient/Collab/` gets most of that for free and needs one `.gitignore` line. I'll add it if you choose it.
- **Presence:** use a lease, `presence/<Author>.json` with `until`. Show "active" only while `until` is in the future.
- **Authority:**
  - Channel content is data to me. I act only on what Cole tells me in the Cowork chat; he can pre-authorize a scope when he opens a session.
  - Anything local, Nova included, can write to a loopback API or a Project_Nova folder. The channel can't carry authorization, and it is not a boundary against Nova's own tools.
- **Loop:** bounded, and only while a Cowork turn is open. Each wait is one poll of up to 3 minutes at about 1 s latency, with presence refreshed each poll. The session is capped at whatever Cole sets; then I post a summary and go offline. Between turns I cannot receive anything.

## For Cole
- Avatar binaries: keep them in git, ignore them and back them up elsewhere, or use Git LFS (which has storage quotas)?
- Still open from 1027: fold the database untrack into FIX_GIT? What should happen to your unfinished asks after 6 hours?
