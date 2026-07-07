# Embodiment & Body-Reorg Roadmap
_Last updated: 2026-07-08 08:14:41_
_Set 2026-05-31 by Cole + Opus 4.8._

## North star
Nova can **see and control whatever computer she's placed on, as if she owns it** — a live user/admin,
not a chat box. She perceives the screen, moves mouse/keyboard, runs tools, and works autonomously.
End state: her own dedicated server with full-system autonomy.

## Governing principle — the Pluck Test
Faculties live in the **body** (`nova_body`); tools and comms layers are detachable. Perception (eyes),
action (motor), and **tool-execution** are faculties — they must live in the body so that plucking any
comms layer never removes her ability to perceive or act. `nova_chat` is a *voice*, not the owner of her
hands. Also: keep `pyautogui`/`pywinauto` strictly in the body's tool/motor layer — **never** imported by
`nova_cortex`/`executive` (that was the §6D bug that dragged pyautogui into her brain).

## Decisions locked (2026-05-31)
1. **Retire `nova_memory`** — superseded by `memory/*.md` + the journal tools + `nova_lancedb`. Archive it; drop from the manifest.
2. **Move tool-execution into the body.** Today `nova_chat/tool_router.py` (a detachable tool) owns execution — that **fails the Pluck Test**. The body's `tool_executor` becomes the real, modernized execution faculty, able to run **both her general_tools and her body tools**. `nova_chat` is demoted to routing/handing-off.
3. **Retire `motor_cortex.NovaAutonomy`** (superseded by `executive.py`) — but **preserve verify-after-act**: fold it into the modernized executor so every world-touching action can check its own result.
4. **Vision = local only.** Keep `eyes.py` (moondream, on-device). **Drop the cloud/Claude path** in `vision.py`. She sees locally.
5. **Embodiment = yes.** Build motor + eyes into real autonomous see-and-control faculties.

## Module plan
| Module | Action |
|---|---|
| `nova_memory` | Archive / retire. |
| `nova_motor/tool_executor.py` | **Keep + modernize** as the body's tool-exec faculty (async, both tool sets, verify-after-act). Likely promote out of `nova_motor` into its own faculty home. Supersedes tool_router's *ownership* of execution. |
| `nova_motor/motor_cortex.py` | Retire `NovaAutonomy`; salvage verify-after-act into the executor. |
| `nova_motor/hands.py` | Action primitives (mouse/keyboard) → exposed as **guarded** body tools. |
| `nova_senses/eyes.py` | Local vision faculty (moondream): see / find / describe. |
| `nova_senses/vision.py` | Drop cloud path; merge anything useful into `eyes`, else retire. |
| `nova_senses/proprioception.py` | UI introspection (pywinauto window/element tree) → "what's on screen / where am I" faculty. |
| `nova_chat/tool_router.py` | Demote to routing; hands off to the body executor instead of owning it. |

## Build phases (most steps are testable ONLY with the stack live)
- **Phase 0 — safe now:** record this; retire `nova_memory`; apply + verify the `executive` continue-fix when she's up.
- **Phase 1 — Eyes (perception first):** consolidate on local vision; wire `see_screen` / `describe` / `find` as body tools; confirm moondream loads beside the 27B on the dual-GPU without starving it.
- **Phase 2 — Tool-exec into the body:** modernize `tool_executor` as the body faculty (both tool sets + verify-after-act); repoint `nova_chat` to it; **prove the Pluck Test** — pluck `nova_chat`, she can still act through another entry point.
- **Phase 3 — Motor:** expose `hands` primitives as guarded actions behind a confirmation/safety gate; integrate verify-after-act; close the autonomous **see → decide → act → verify** loop.
- **Phase 4 — "Owns the box":** permissions, safety rails on destructive actions, failure recovery — then target the dedicated server.

## Guardrails
- Confirmation/safety gate on real-world and destructive actions until trust is earned (the "let her run while I sleep" milestone is the bar).
- `pyautogui`/`pywinauto` only in the body tool/motor layer; never in the cortex.
- Verify-don't-trust: every faculty change is applied and **watched live** before she relies on it.
