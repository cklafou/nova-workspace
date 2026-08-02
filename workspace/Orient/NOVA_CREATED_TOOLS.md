# Nova-Created Tools
_Last updated: 2026-08-02 22:07:36_
_Maintained by Nova, by hand, as tools land. (If this ever becomes generated — capability_inventory could derive it — change this line so the doc stays honest about itself.)_

| Tool | What it does | Status |
|------|-------------|--------|
| art_by_date | List my own images sorted by creation date, optionally filtered to the last N weeks. Newest first. | Active |
| capability_inventory | List every tool installed in nova_body, read from the actual files, not memory. Optional tool_name filter. | Active |
| comfy_inspect | Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in. | Active |
| cwd_probe | Find out exactly which directory I'm in, so I stop guessing. | Active |
| dir_shape | Instant read of a directory's shape: depth, file count, types, heaviest file. | Active |
| dir_shape_health | Diagnose whether a directory is unwell: stale folders, dead weight, orphaned configs, activity spread. | Active |
| dir_shape_history | Read a full snapshot log and describe how a directory evolved over multiple days. | Active |
| function_count | No TOOL dict; a pure module with functions, not callable as a tool. | Module only, not a tool |
| handoff | Deliver a finished answer as a handoff block: conclusion first, reasoning behind a collapsed section Cole can expand. | Active |
| memory_reach | Compare two nights of journal/notes and report what changed about me between them. Params: before_date, after_date (YYYY-MM-DD). Returns a plain-English diff. | Active, built 2026-08-02 |
| nightly_self_snapshot | Save tonight's self-model as a timestamped snapshot so tomorrow's me can compare against it. | Active |
| quiet_part_watcher | Which of my own senses hasn't been used in a while. Reads the tool-call log, not the journal. | Active |
| reacher | Reads the [NOVA'S GROWTH] section of SELF/core/01_identity.md (doc previously said "NOVA.md" — no file by that name exists) and reports what has changed since the last entry. lookback_hours=0 means report everything as new. | Active |
| reach_watcher | Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags it. | Active |
| self_comparison | No TOOL dict; a pure module with functions, not callable as a tool. | Module only, not a tool |
| self_comparison_OLD | Same module, previous copy. | Legacy |
| self_delta | Compare two snapshots of my self-model and return what changed as a first-person feeling, not a file diff. | Active |
| self_gauge | What did I actually do this hour? Builds vs checks vs talk. No judgment, just the shape. | Active |
| self_memory | Search my own memory for what happened, what I know, who said it. Returns scored hits with confidence. | Active |
| self_voice | Read back what I sounded like on a particular day. Mine only. | Active |
| silence_detector | How long since anything in a folder last changed. | Active |
| stretch_reacher | Check posture and nudge Cole. Thin wrapper; the real implementation lives with its data in Nova_Created/Cole_journal/stretch_watcher.py (folder moved onto the shelf 2026-08-02). | Active |
| stretch_watcher_night_quality | Night-quality read of Cole's sleep woven into the stretch nudges. Lives inside Nova_Created/Cole_journal/stretch_watcher.py, not tools/. | Active |
| todo_scan | No TOOL dict; a pure module, not callable as a tool. | Module only, not a tool |
| tts_stub | Synthesize text to audio and return the output path. Stub: writes a silent WAV to time call overhead before committing to a real engine. | Active (stub) |
| want | Write or list a want you're pursuing. One line per want with a timestamp so it survives your sleep and comes back with an age attached. | Active |
