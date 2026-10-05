<!-- @nova: Record transcript lifetime protection discovered during the continuation integration review. -->
# Conversation transcript pins

**Summary:** Independent review found that retaining an old conversation's Transcript reference was insufficient: switching away compressed and deleted its raw JSONL, then a queued reply could recreate a tail-only file. A switch back could also create a second in-memory Transcript whose later flush overwrote the old object's reply.

## Did
- `workspace/general_tools/nova_chat/session_manager.py`: added `retain(session_id, transcript)` and `release(session_id, transcript)` with reference counts and exact identity validation. Pinned sessions keep the same Transcript when selected again, retain their raw JSONL while work is outstanding, and refuse archive/delete. The final release of an inactive session flushes and compresses it.
- Gzip publication, decompression, and index replacement now use sibling temporary files before rename. Failed gzip publication preserves the complete raw log. New sessions created within the same second receive distinct IDs rather than overwriting one another's metadata.
- Root owns the corresponding admission/terminal hooks in server.py and Orient explanations. No live session records were modified by this work.

## Verified
Six tests in `workspace/general_tools/nova_chat/tests/test_session_pins.py` use the real Transcript and SessionManager with temporary paths. Cases cover two outstanding references, a queued reply after switching away, switching back before the final reply, exact identity/repeated release checks, archive/delete protection, failed gzip publication, and same-second session creation. All six pass; scoped diff check passes.

## Review handoff
Also reported to root for its owned source: response events need the original conversation identity so a queued old-conversation reply does not render in the selected conversation; grounding should use the frozen transcript rather than globally selected messages; the unthrottle notification must not yield before ordered admission. An explicit scoped Stop currently cancels the shared active turn, including accepted aliases; this differs from merely ending audio playback and should be described accurately. No speculative provider or witness changes were made.
