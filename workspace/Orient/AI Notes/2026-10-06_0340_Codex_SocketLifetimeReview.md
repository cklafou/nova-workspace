<!-- @nova: Record source review of removing WebSocket-driven worker shutdown while retaining explicit launcher-owned lifecycle. -->
# Socket lifetime review
**Summary:** Removing the legacy last-WebSocket watchdog is consistent with launcher ownership of the app lifecycle. An ordinary voice/headless/browser disconnect is not proof that the app was quit.

## Reviewed
- Root removed `_window_close_watchdog` and its normal/chat-only startup scheduling from `workspace/general_tools/nova_chat/server.py`. No other last-client shutdown path found in that module.
- WebSocket disconnect now only removes the connection and may drain accepted pending input; it does not kill the worker.
- Explicit `/shutdown` and `/api/services/shutdown` still stop active work and forward shutdown to the launcher hub. The one-second acknowledgement grace and launcher ready-gate watcher remain.
- `nova_chat/desktop.py::quit_app` saves state, closes its owned windows and quits Qt. The launcher waits for its owned app process and performs teardown in `finally`. Closing the normal native window hides to tray; explicit Quit remains the shutdown action.
- Browser handoff still waits for the server and needs explicit Stop/Quit; this review does not restore the removed browser-close heuristic.

## Offline verification
- Chat-only tests:7 passed.
- Lifecycle acknowledgement tests:3 passed (with workspace on PYTHONPATH).
- Launcher-mode tests:18 passed,1 errored. Its disposable loopback HTTP HubRoutes fixture twice raised Windows10053 connection-aborted, at different request positions. That result is not counted as passed and was reported to root. No corresponding modified hub/launcher code exists in this narrow change; cause was not established here.
- No actual Nova/model process controls, provider calls or production edits by this reviewer. Root owns the live disconnect-and-wait survival check.

## Source receipt
Server SHA256 at 2026-10-06T03:40:07.417650+09:00: `84047dcfa211526803e3b66d5d7fa6f1b7bceca65b5acf635c8fbfa742836dbc`. This is source identity, not proof it has loaded.
