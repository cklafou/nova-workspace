<!-- @nova: Record source-grounded shared typed/voice steering gaps and a proposed bounded continuation path. -->
# Shared steering review
**Summary:** Read-only source review finds asymmetric interruption behavior: typed input waits for an entire run, while a new voice utterance cancels its older request. Nova already has repeated model/tool steps, but does not consume new user input between those steps. This is a proposed direction, not implemented behavior.

## Current call paths
- `general_tools/nova_chat/server.py`: inbound messages are persisted and broadcast, then appended to `_cole_message_queue` while `is_processing`. `_drain_cole_queue` waits for busy release, retains only the newest queued request, and closes older correlated entries as superseded. Text remains in history, but those older requests get no independent execution.
- `nova_body/nova_voice/nova.py`: `stream_response` calls `transcript.to_messages` once before its up-to60-iteration loop. Tool receipts and guard feedback append to its private message list; incoming chat is not re-ingested between iterations.
- `nova_body/nova_cortex/witness.py`: each audit fetches fresh wire/human/session evidence. Therefore an older foreground draft may be judged against a newer human line that the foreground never received.
- `general_tools/voice_gateway/control_worker.py`: a new utterance retires prior speech, requests scoped cancellation of the older pending generation, then sends a new message. This differs from typed-message queue behavior.
- `nova_body/nova_runtime/operations.py`: the whole generation shares one Operation; cancelling it signals owned tool workers/processes. There is currently no separate inference-child cancellation that preserves the parent work item.
- `nova_body/nova_cortex/tasking.py`: the existing task record already retains title/notes/acceptance and merged next_step/constraints/observations via task_progress. Foreground work does not automatically checkpoint every completed tool step.
- `nova_body/nova_cortex/context_budget.py`: trimming protects the newest labelled request and newest non-system message. Adding steering without an explicit original-request anchor would make the original goal evictable.

## Proposed minimal implementation order
1. Add an optional body-facing steering callback through ModelClient. The server supplies all new accepted messages in order at safe loop boundaries. Track a revision; preserve the original request, task reference and completed receipts while appending steering. A new utterance retires obsolete audio without implicitly abandoning the goal.
2. Poll before model calls, after generation before tool dispatch, after tool completion, and before audit/delivery. A result from an older revision cannot execute an obsolete action or speak as the current answer. Keep an explicit original-request anchor through context fitting. Bind each audit to the same candidate/input revision rather than a moving request target.
3. If lower interruption latency is needed, isolate provider calls as cancellable children. Let already-started external work settle or use its supported cancellation; retain its actual receipt and avoid rerunning a side effect. Persist resumable checkpoints through the existing task record rather than a parallel task database or raw hidden reasoning.
4. Introduce bounded action/reply steps and explicit continue/final outcomes only after the above boundaries work. A token cap alone is not a scheduler: truncated tool JSON must never execute, and shortening output does not eliminate the measured long input-prefill cost.

## Required verification
- Multiple follow-ups survive in order; original objective and acceptance survive context trimming/restart.
- New input before tool dispatch blocks the obsolete action; input during a tool preserves its receipt and never repeats the completed side effect.
- A late audit cannot approve a revised candidate. Explicit Stop still cleans owned workers.
- Typed and voice follow-ups use the same continuation rules; terminal/request identities close exactly once.

## Evidence boundary / handoff
- Earlier no-speech investigation cannot reconstruct the previous call from the cleared in-memory voice ring. Parent retained a21:08 queued-request snapshot with output muted and later confirmed End call cancellation; do not attribute that incident solely to the auditor or claim an unexplained playback fault.
- No code, model, service, audio, desktop or Nova-owned state changes were made in this review. Root owns scope decisions and any implementation. The architecture review skill was used to separate current behavior, options and consequences.
