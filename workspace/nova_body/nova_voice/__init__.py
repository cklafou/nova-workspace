"""nova_voice — her MOUTH and her HANDS, moved body-ward 2026-07-20.

THE PLUCK TEST, FINALLY PASSED
    Cole's governing rule: delete the chat server and she still lives, thinks, and acts.
    Faculties live in nova_body/; faces detach.

    Since 2026-07-14 the body passed that test for thinking, remembering and perceiving —
    and FAILED it for speaking and acting:

        model client (her mouth):   *** UNREACHABLE — No module named 'nova_chat'
        tool_router  (her hands):   *** UNREACHABLE — No module named 'nova_chat'

    Pluck the chat server and she could think, remember and feel — and could not say a word
    or lift a finger. The 07-19 audit named it and deliberately did not fix it mid-test.

WHY THE MOVE WAS SMALL IN THE END
    Both files were already body-clean. tool_router.py imported nothing but `pathlib`.
    nova.py reached into the face exactly ONCE — `from nova_chat.tool_router import
    execute_tool`, a sibling reaching sideways. The organs were never entangled with the
    server; they were merely filed under it. What looked like a refactor was a move.

    A stale comment in runtime.py claimed nova_client was "a leaf module (stdlib + httpx, no
    chat-server deps), so importing it here doesn't drag the server in." That stopped being
    true when the tool_router import landed. It is true again now.
"""
