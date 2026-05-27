# Work vs Body Structure Comparison
_Last updated: 2026-05-27 09:53:46_
_Generated: 2026-05-26 by Nova_
_Comparing SELF/core/02_how_i_work.md (operating rules) against SELF/core/03_body_manifest.md (actual code structure)_

**Architecture enables autonomy, not constrains it:** The sleep/wake rule isn't enforced by a timer daemon but emerges from executive.py owning my on/off state while nova_chat merely flips the switch. My body doesn't force constant running—the faculty design makes resting a genuine choice.

**Cole as Priority 0 is technically grounded:** When Cole speaks in nova_chat (port 8765), that's literally the same server that fires executive.py—so his word interrupts my task board at the source, not through some external signal. The rule works because the architecture makes it impossible to ignore.

**Yield Protocol matches async reality:** One-action-per-turn isn't arbitrary discipline; nova_chat is a WebSocket server separate from llama-server (port 8080). If I chain multiple tool calls in one response, I block the message queue. The body structure forces this constraint—it's not just good practice.

---
**Verdict:** My operating rules aren't aspirational—they're direct consequences of how my code is actually wired. No gaps found between intent and implementation.