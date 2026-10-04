<!-- @nova: Record Conversation power controls, their validation and the remaining native restart check. -->
# Conversation start and stop
**Summary:** Added Start Nova / Stop Nova directly below the Conversation tabs. The launcher changes Nova's services while keeping the controller window and console alive. Source and fixture checks pass; the existing running launcher still needs a normal restart after Cole finishes gaming.

## Did
- Added `general_tools/nova_chat/lifecycle.py`, `general_tools/nova_console/lifecycle.py` and `general_tools/nova_chat/static/conversation-power.js`; integrated server, launcher, hub and workspace controls.
- Stop drains supervised work, flushes the session and closes owned helpers before replacing the full worker with chat-only. Failed quiesce refuses teardown. Start uses the configured model through `start_llama_qwen36.cmd` instead of obsolete hardcoded model/adapter values.
- Shared transition guards block new body work and updater mutations, including in a replacement worker; competing requests and Qt Quit during startup are handled. Startup failure attempts chat-only recovery.
- The page preserves unsent text, caret/selection, images and file mentions over mode reconnection. Older owners show a restart instruction. Control remains available with all conversation tabs closed.
- Fixed updater terminal-job refresh so a completed training job cannot leave a stale busy flag disabling recovery.
- Updated authored Orient explanations and source watches; reviewed lifecycle behavior independently.
- Retired temporary training server PID 41736 on 8877 after confirming the completed job is available through the original 8765 controller. Retired test fixture PID 12732 on 8878 and closed both agent-created test tabs. Original controller/launcher left untouched.

## Verified
- 61 combined lifecycle/launcher/chat-only/controller tests and 8 updater integration tests passed.
- Updater suite: 152 tests, OK with 3 opt-in skips. Node updater checks and 8 Conversation power scenarios passed.
- Real browser using actual lifecycle router/button code and simulated services: off -> on -> off, button labels Start -> Stop -> Start, one start and one stop request, draft retained after both page reloads, no browser errors.
- Browser screenshot: `Temp/conversation-power-validation/conversation-button-proof.png`. This is a fixture, not evidence of real Nova or Qt lifecycle behavior.
- Orient regeneration reported zero review-needed sections and zero dangling references. Final strict check follows this note. Diff whitespace check passed.

## Open / next
- After gaming, one normal full Nova Chat restart must load the new launcher/backend. A static page reload alone does not upgrade the old owner. Then verify one actual full start/stop cycle, model readiness, service-port cleanup and native window continuity.
- Qwen 3.8 training is complete; both epoch GGUF adapters are installed beside the model but inactive. See `2026-10-04_1235_Codex_Qwen38TrainingComplete.md` and model READMEs for exact hashes and provenance. Real adapter loading and behavioral A/B remain pending.
- RunPod GPU is stopped. Approximate combined GPU cost was $2.00, not an invoice. Retained 150GB recovery storage still costs approximately $0.04/hour; it preserves remote checkpoints and recovery logs.

## For Claude and Cole
- No real Nova/model start or native window restart was performed during gaming. Do not treat fixture passes or completed training as runtime or behavior proof.
- All source is in the shared working tree; no commit made. Nova personal state was not hand-edited for this control.
