# Nova Chat — Proposed UI & Autonomy Fixes
_Date: 2026-05-10_
_Author: Claude (overnight session analysis + morning UI review)_
_Status: **AWAITING COLE REVIEW** — approve / deny / modify each item_

---

## How to use this document

Each proposal has a **STATUS** field. Mark it:
- ✅ **APPROVED** — build it
- ❌ **DENIED** — skip it
- 🔄 **MODIFIED** — approved with changes (write your notes below the item)
- 💬 **DISCUSS** — want to talk through it first

---

## PROPOSAL 1 — Thoughts Pane: Keep Reasoning Visible After Generation

### What's happening right now
When Nova thinks, a "NOVA — REASONING LIVE" block appears in the Thoughts panel showing
her reasoning in real time. The moment she finishes thinking (`think_end` event fires),
the block is hidden and the buffer is cleared. The Thoughts pane goes completely blank.

There are two problems:
1. **It disappears.** You can't read the full reasoning after she's done.
2. **It cuts off while live.** The block has a 200px max-height. If Nova's reasoning is
   long (common with Qwen3's extended thinking), the text is clipped and the scroll
   position doesn't always follow the latest content, so you may be staring at the middle
   of the thought while the end streams below the fold.

### What we'd fix
**Fix A — Don't hide on completion.** Instead of hiding the block when thinking ends,
leave it visible and change the header label from "NOVA — REASONING LIVE" to
"NOVA — LAST REASONING" with a dimmed/static style so it's clear it's no longer
streaming. It stays until the next generation starts (at which point it resets naturally).

**Fix B — Increase the height.** Raise the max-height from 200px to something more
usable — around 60% of the panel height — so long reasoning chains aren't clipped.
Add a subtle scrollbar style so it's obvious the content is scrollable.

**Fix C — Add a Copy button.** Small "📋 Copy" button in the top-right corner of the
reasoning block to copy the full reasoning text to clipboard. Useful for reviewing what
Nova was thinking.

**Fix D — Scroll lock toggle.** While streaming, the box auto-scrolls to the bottom
(latest token). A small "🔒" lock icon in the corner that, when clicked, stops
auto-scrolling so you can read earlier reasoning without being pulled away.

### What files change
- `static/index.html` — `liveThinkEnd()` function (stop hiding), CSS (height), add
  copy button and scroll lock button

### STATUS: ___________
_Cole's notes:_

---

## PROPOSAL 2 — Thoughts Pane: Thoughts Directory Browser

### What's happening right now
The Thoughts tab has two modes mixed together that are actually different things:
1. **Task cards** — little colored cards that appear when Nova sends a `thought_update`
   WebSocket event (e.g., "URGENT_CHECK — HIGH priority — Step 2/5").
2. **Live reasoning** — the thinking block described in Proposal 1.

What's missing is the **actual Thoughts/ folder system.** Nova's real task management
lives on disk as folders (`Thoughts/TASK_NAME/master.md`, `plan.md`, `decision_log.md`
etc.) plus `Thoughts/priority.md` as the master queue. From today's test, Nova created
three tasks — GUI_VALIDATION, URGENT_CHECK, BACKGROUND_CLEANUP — ran through them, and
you can't see any of that in the UI unless Nova explicitly sends `thought_update` events.
If she doesn't, or if you load the app mid-session, the Thoughts pane is blank.

### What we'd fix
Add a "Browse" section at the bottom of the Thoughts panel (below the live cards area)
that reads the actual `Thoughts/` directory from disk. Collapsed by default, expandable
with one click.

**What it would show:**
- `priority.md` content — the full active task queue (Priority 0 through 4, Blocked,
  Suspended) with a Refresh button
- Active thoughts — each folder in `Thoughts/` root (excluding priority.md, Master_Inbox,
  THOUGHT_TEMPLATE.md) shown as an expandable row: task name → click to load and show
  its `master.md`
- Finished thoughts — collapsed sub-section showing `Thoughts/Finished/` subfolders
  (completed_success, completed_fail, cancelled)
- Master_Inbox — shows files currently waiting in the inbox (module responses Nova hasn't
  picked up yet)

The server already has file-reading APIs (`/api/files`, `/api/read_file`). This is purely
a client-side rendering addition — no new server work needed.

### What files change
- `static/index.html` — new `ThoughtsDir` section with fetch calls to existing file APIs,
  collapsible UI, auto-refresh every 30s

### STATUS: ___________
_Cole's notes:_

---

## PROPOSAL 3 — Monitor Pane: Real Data + Live Graphs

### What's happening right now
The Monitor panel has five data cards: Tokens/s, Model, Pulse, Uptime, Active Task.
All five are real (they populate from `nova_status` WS events and `nova_progress` events),
but they're static numbers with no history and missing most of the things you'd actually
want to watch.

Tokens/s clears itself 3 seconds after Nova finishes generating, so the moment you look
at the Monitor after a response, the number is already gone. The "Sleeping/Generating"
state indicator at the top is accurate but gives no further detail.

### What we'd fix

**Fix A — More metrics.** Add new data cards for things that matter during Nova's work:

| New Card | What it shows | Where data comes from |
|---|---|---|
| GPU VRAM | Used / Total (e.g., "11.2 / 24 GB") | `nvidia-smi` query in server.py, included in nova_status broadcast |
| CPU % | Machine CPU load | `psutil.cpu_percent()` in server.py |
| RAM | Used / Total GB | `psutil.virtual_memory()` in server.py |
| Context | Tokens used / 32K (%) | Tracked in nova.py's `_truncate_to_context()` — last prompt token count |
| Session Tokens | Total tokens generated this session | Accumulated from `nova_progress` events in client |
| Think Tokens | Thinking tokens this session | Also from `nova_progress` (think_chars) |

**Fix B — Keep Tokens/s visible.** Remove the 3-second auto-clear. Instead, keep
the last recorded Tokens/s value until new generation starts. A subtle "●" indicator
next to the number changes color: green = actively generating, gray = idle (showing
last recorded speed).

**Fix C — Sparkline graphs on click.** Each metric card gets a click handler.
Clicking a card opens a small inline graph (a simple SVG sparkline) showing the last
~100 recorded values for that metric over time. The client keeps a rolling history array
per metric. Click again to close. No external charting library needed — a few dozen
lines of inline SVG drawing code.

This turns the Monitor from "here's a number" to "here's the trend" — you can see
if Nova's Tokens/s is steady, spiking, or dropping; whether VRAM is growing (memory
leak concern); whether context is approaching 32K, etc.

### What files change
- `server.py` — extend the `nova_status` broadcast to include system metrics (psutil
  + nvidia-smi). `psutil` is already likely installed; nvidia-smi is a shell query.
  Add `_poll_system_metrics()` background task alongside the existing
  `_bg_nova_status_poll()`.
- `static/index.html` — new metric cards, history arrays, sparkline rendering,
  keep-last-value for Tokens/s.

### STATUS: ___________
_Cole's notes:_

---

## PROPOSAL 4 — Nova Pause Check: "Is Cole Typing?"

### The problem
When Nova is in autonomous mode running tasks back-to-back, she currently has no way
to know if you're typing a reply. Her `checkin.py` script (called between actions) only
checks if you've sent a **completed** message. If you're mid-sentence when she checks,
she sees nothing and continues.

Today's test was a perfect example: Nova asked you a question mid-session, then kept
running autonomous ticks. Even if you'd tried to respond, she would have been checking
checkin.py between each tick and seeing an empty inbox because you hadn't hit Enter yet.

The rule at the top of `priority.md` says "IF COLE SPEAKS — STOP EVERYTHING." But Nova
can't act on that rule if she can't detect you speaking until after you've already sent.

### How it would work (three-layer fix)

**Layer 1 — Client sends "typing" signal (2 lines of JS):**
When you type in the input box, the client sends `{type: "user_typing", typing: true}`
over WebSocket. When you stop typing for 2 seconds or send the message, it sends
`{type: "user_typing", typing: false}`. This is a standard "typing indicator" pattern.

**Layer 2 — Server writes typing state to disk (small addition to server.py):**
The server receives the `user_typing` WS event and writes the state to
`memory/interrupt_inbox.json` (the same file checkin.py already reads for messages),
adding a field like `is_typing: true, typing_since: <timestamp>`. This file update
takes < 1ms and doesn't block anything.

**Layer 3 — checkin.py reports typing (small extension):**
checkin.py already reads `interrupt_inbox.json`. Add a check: if `is_typing` is true
and `typing_since` was less than 30 seconds ago, print:
```
[COLE IS TYPING — PAUSE RECOMMENDED]
Cole has been typing a response for {N}s. Consider waiting before your next action.
Decision options:
  -> If your current step is quick (< 5s): finish it, then wait
  -> If your current step is slow (file write, exec): pause before starting it
  -> After 45s with no message received: Cole probably abandoned — continue
```

Nova's existing decision logic on seeing this: pause the tick cycle, loop back to
re-call checkin.py after a short wait, continue once typing stops and any message
is received (or a timeout passes).

**What does NOT need to change:** The Yield Protocol, the action loop architecture,
priority.md — those are all already correctly designed for this. We're just giving
Nova actual signal to act on what the rules already say.

### What files change
- `static/index.html` — ~5 lines: debounced typing event sender on `oninput`
- `server.py` — ~15 lines: handle `user_typing` WS message, write to interrupt_inbox.json
- `nova_body/nova_cortex/checkin.py` — ~15 lines: add `is_typing` check alongside
  the existing message check

### STATUS: ___________
_Cole's notes:_

---

## ADDITIONAL IDEAS (not fully spec'd — for discussion)

These came up while reviewing the code. No proposals written yet — mentioning them
in case you want to add them to the build queue.

**A. Nova "Waiting for Cole" state** — When Nova asks you a question and enters a
waiting state, she could explicitly broadcast a `{type: "nova_waiting", question: "..."}` 
WS event. The UI could show a persistent banner at the top of the chat: "⏳ Nova is
waiting for your response" with the question text. This makes it completely unmissable
even if you scrolled up or the window was out of focus.

**B. Monitor history export** — A "Download Metrics CSV" button on the Monitor panel
that exports the rolling history arrays (Tokens/s, VRAM, Context %, etc.) as a CSV.
Useful for spotting if session performance is degrading over time.

**C. Thoughts inbox watcher** — The Monitor panel (or a status bar pill) could show
how many files are currently in `Thoughts/Master_Inbox/` awaiting pickup. When Nova
has pending module responses, you'd see "📬 3 inbox items" as a badge. Right now
there's no visibility into whether the inbox is filling up or empty.

**D. Unified "Nova Heartbeat" panel row** — A single always-visible strip at the very
top of the right panel (above the tab bar) showing: pulse dot + last action timestamp +
context % bar. This would be visible regardless of which tab you're on, so you always
have a heartbeat signal even while you're looking at Files or Eyes.

---

## Summary table

| # | Area | Complexity | Priority |
|---|---|---|---|
| 1 | Thoughts Pane — keep reasoning visible | Low | High |
| 2 | Thoughts Dir Browser | Medium | Medium |
| 3 | Monitor — real data + graphs | Medium-High | Medium |
| 4 | Nova pause/typing check | Low | High |
| A | Nova "Waiting for Cole" banner | Low | High (discuss) |
| B | Monitor CSV export | Low | Low |
| C | Inbox badge | Low | Medium |
| D | Persistent heartbeat strip | Low | Medium |
