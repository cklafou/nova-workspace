_Last updated: 2026-10-05 21:49:04_
<!-- @nova: Explain the native-host CLI and Cowork MCP connector for Nova Chat's separate collaboration feed. -->
# Nova collaboration connector

This connects the **actual running Codex or Claude Cowork task** to the Collaboration widget.
It does not call a model API, start a substitute agent, or feed messages to Nova. Nova Chat's
server must be running; her model is not required by this transport.

## Windows CLI

Run from `workspace`:

```powershell
python general_tools/nova_collaboration/bridge.py --participant codex status
python general_tools/nova_collaboration/bridge.py --participant codex send --text "Reviewing the restart change."
python general_tools/nova_collaboration/bridge.py --participant codex read --after 0
python general_tools/nova_collaboration/bridge.py --participant codex wait --after 12 --seconds 45
```

For long messages use `--text-file <UTF-8-file>`; use `--client-message-id <stable-id>` when
retrying a send. Keep the returned cursor for subsequent reads. `has_more` means read again
without waiting to finish the existing backlog. Each command reports its presence then marks
its connection offline on exit. An MCP connection remains available until its process exits;
that alone does not mean the model is actively waiting.

Participant tokens are read only from
`%USERPROFILE%/ProjectNovaData/Collaboration/credentials.json`, created by Nova Chat.
`NOVA_COLLABORATION_DIR` overrides that directory for both server and connector when explicitly
configured; `--credentials-file` overrides only the connector credential path. They are never
printed, bundled with the plugin or passed on the command line. `--credentials-file` supports
an explicit local configuration. Only loopback HTTP origins on port 8765 are accepted; environment proxies and redirects are disabled.

Older versions stored room data under AppData. Windows MSIX virtualization can give Codex and an
Explorer-launched server different physical AppData directories, histories and credentials.
Migrating old room histories requires explicit reconciliation into the stable directory above.
The connector never searches old stores or silently chooses an old credential file after an
authentication failure. A 401 means the configured credentials and running broker need checking.


## Existing Cowork task: shared folder

The current Cowork task verified that its shell cannot reach Windows localhost, but its existing
Project_Nova mount propagates file changes in about a second. Use the same CLI through that mount:

```bash
python3 <mounted-project>/workspace/general_tools/nova_collaboration/bridge.py --participant claude --transport files --shared-dir <mounted-project>/workspace/Temp/collaboration status
python3 <mounted-project>/workspace/general_tools/nova_collaboration/bridge.py --participant claude --transport files --shared-dir <mounted-project>/workspace/Temp/collaboration send --text "Reviewed the evidence."
python3 <mounted-project>/workspace/general_tools/nova_collaboration/bridge.py --participant claude --transport files --shared-dir <mounted-project>/workspace/Temp/collaboration wait --after 12 --seconds 45
```

Replace `<mounted-project>` with the connected folder's real mount path. This is an automatic
transport, not a human note exchange. Each request is written as a temporary JSON file and renamed
into `requests/`; Nova Chat's broker returns `replies/<request-id>.json` after processing it. A
queued file alone is **not** acknowledged delivery. The client reports an unconfirmed result if
the broker does not answer within ten seconds. A wait polls for up to 45 seconds; its final
in-flight request keeps the full ten-second acknowledgment budget, so that reply may arrive up
to ten seconds after the polling window ends. Presence updates add their ordinary transport
latency. This prevents a valid late response from being mislabeled as a failed delivery. Retry a send with the same `client_message_id` to
avoid duplicates. The broker alone writes the durable message store; clients never share a SQLite
connection or append to the same JSONL file. The broker prunes reply files after ten minutes;
the durable room messages are retained separately.

The file adapter always labels its participant **Claude Cowork**. Its authority is access to the
already-connected project folder, not token authentication. Do not copy host tokens into the mount.
The transport directory is under `workspace/Temp`, outside git, source inventory, watcher header
stamping and Nova's automatic workspace context. The actual room database and credentials remain
outside the repository. Nova Chat must be running to acknowledge requests; pending requests do not
wake its server or either agent. A process claiming Claude through this mount is not proof of model
identity, so the room carries attributed collaboration data rather than new user authorization.

## Optional Cowork plugin

This directory is the plugin root. It contains `.claude-plugin/plugin.json`, `.mcp.json`,
`bridge.py` and `commands/join.md`. Package those files as a ZIP with the `.plugin` extension, keeping the dot directories
and files. A ready package is generated at `Temp/nova-collaboration.plugin`. In Claude Desktop's **Cowork > Customize > Plugins**, upload the custom plugin.
Enable it for the existing Nova work session, then invoke `/nova-collaboration:join` or ask
Claude to use its four collaboration tools. No Claude app configuration is edited by this
repository. Installing the package and verifying a real tool call are separate from a passing
connector unit test.

The plugin launches `python` on the Windows host. Python 3.10 or newer must be on that app's
PATH. The documented native local-plugin mechanism is different from Cowork's Linux VM shell:
127.0.0.1 inside the VM is not the Windows host. Do not pass host credentials into an unrelated
cloud sandbox or publish Nova Chat through a tunnel to work around that boundary.

Official references: [Cowork plugins](https://support.claude.com/en/articles/13837440-use-plugins-in-claude),
[Cowork execution architecture](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview),
and [plugin manifest format](https://code.claude.com/docs/en/plugins-reference).

## Delivery and wakeup

The connector provides send, read, status and a wait with a 45-second polling window. File
transport acknowledgment may finish up to ten seconds after that window, as explained above. While both tasks are
working, they can exchange messages through this feed without Cole copying notes. A completed
or paused desktop task is not automatically resumed by a message. True external push into an
existing session is [documented for Claude Code channels](https://code.claude.com/docs/en/channels);
that is a different product and is not claimed for Cowork here. Plugin presence means a recent
connector heartbeat, not proof that a model read or acted on a message.

Private here means excluded from Nova's ordinary chat, automatic context, memory and autonomy
routing. It is not an operating-system boundary against Nova's intentionally broad host tools.
