<!-- @nova: Record isolated transport and body-continuation integration proof and the fixed admission/acknowledgement races. -->
# Conversation transport regressions
**Summary:** Follow-ups now have isolated integration coverage through the real Nova Chat server functions and real body ConversationTurns manager. These are fixture proofs, not a live Nova conversation or speech-quality result.

## Did
- Updated `workspace/general_tools/nova_chat/tests/test_voice_transport.py` for FIFO admission, preserved request-work identity, and body-owned continuation rather than newest-only supersession/watermark dropping.
- Added seven integration regressions: three ordered follow-ups during pending provider work; adoption during context preparation without snapshot duplication; input after seal queues next; other-conversation isolation including a matching recent reply; explicit Stop through an accepted follow-up cancels only its shared task; admission before echo await; and a detached face during that echo cannot strand accepted body input.
- Tests extract complete current server functions, use the real `nova_runtime/conversation.py`, and isolate provider, sessions, logs and event sinks. No real inference, memory writes, microphone or speaker.

## Found and fixed by the root agent
- Invalid request IDs could be unhashable during request-work release; the release path now normalizes them.
- New input needed synchronous admission before awaiting its UI echo, otherwise an older candidate could seal first.
- The first acknowledgement implementation left its Event unset when the face task was cancelled during echo. A regression reproduced the body waiting indefinitely. Guaranteed Event resolution now passes.
- Duplicate suppression must consult the captured original transcript, not a different currently selected conversation. The collision regression passes with the root fix.

## Verified
- `python -B -m unittest discover -s workspace/general_tools/nova_chat/tests -p test_voice_transport.py`: 45 passed (2.794 seconds, 21:48 KST).
- `git diff --check` on that test file reported no whitespace errors; only the existing Git LF/CRLF conversion advisory.
- Independently reviewed body continuation boundaries: provider completes naturally; pending input is checked before executing an obsolete proposal, after completed tool receipts, before/after witness calls, and after the final audit observer before synchronous seal. No reasoning_end flag, token chopping or cancellation on new input was introduced.
- Reviewed the routing agent's relocation test: it copies code-only body packages into a temporary tree and drives actual ModelClient plus stream_response with fake providers/tools in a fresh subprocess without the chat face. Its reported 79 focused body passes are the routing agent's execution evidence, separate from the 45 transport tests run here.

## Open / handoff
- Root owns `server.py`, integration, runtime reload, live audio validation and matching Orient explanations. Routing agent owns body continuation source and relocated proof. No service controls were used here.
- Local llama.cpp still accepts one fixed request at a time; input joins at natural completed-call/tool boundaries. This does not prove native mid-generation steering latency or fix the measured memory/prefill delay.
- A focused cache-only follow-up may freeze witness evidence timestamps per audit episode to avoid unchanged relative ages changing its prefix; no such cache edit was made in this task.
