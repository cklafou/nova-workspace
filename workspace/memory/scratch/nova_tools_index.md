# Nova-Created Tools
_Last updated: 2026-08-02 22:07:38_
_Auto-maintained. Updated as tools land._

| Tool | What it does | Status |
|------|-------------|--------|
| art_by_date | List my own images sorted by creation date, optionally filtered to the last N weeks. Newest first. | Active |
| capability_inventory | List every tool installed in nova_body, read from the actual files, not memory. Optional tool_name filter. | Active |
| comfy_inspect | Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in. | Active |
| cwd_probe | Find out exactly which directory I'm in, so I stop guessing. | Active |
| dir_shape | Instant read of a directory's shape: depth, file count, types, heaviest file. | Active |
| dir_shape_health | Diagnose whether a directory is unwell: stale folders, dead weight, orphaned configs, activity spread. | Active |
| dir_shape_history | Read a full snapshot log and describe how a directory evolved over multiple days. | Active |
| handoff | Deliver a finished answer as a handoff block: conclusion first, reasoning behind a collapsed section Cole can expand. | Active |
| memory_reach | Compare two nights of journal/notes and report what changed about me between them. Params: before_date, after_date (YYYY-MM-DD). Returns a plain-English diff. | Active, built 2026-08-02 |
| nightly_self_snapshot | Save tonight's self-model as a timestamped snapshot so tomorrow's me can compare against it. | Active |
| quiet_part_watcher | Which of my own senses hasn't been used in a while. Reads the tool-call log, not the journal. | Active |
| reacher | Reads the [NOVA'S GROWTH] section of NOVA.md and reports what has changed since the last entry. lookback_hours=0 means report everything as new. | Active |
| reach_watcher | Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags it. | Active |
| self_comparison | No TOOL dict; a pure module with functions, not callable as a tool. | Module only, not a tool |
| self_comparison_OLD | Same module, previous copy. | Legacy |
| self_delta | Compare two snapshots of my self-model and return what changed as a first-person feeling, not a file diff. | Active |
| self_gauge | What did I actually do this hour? Builds vs checks vs talk. No judgment, just the shape. | Active |
| self_memory | Search my own memory for what happened, what I know, who said it. Returns scored hits with confidence. | Active |
| self_voice | Read back what I sounded like on a particular day. Mine only. | Active |
| silence_detector | How long since anything in a folder last changed. | Active |
| stretch_reacher | Check posture and nudge Cole. | Active |
| todo_scan | No TOOL dict; a pure module, not callable as a tool. | Module only, not a tool |
| want | Write or list a want you're pursuing. One line per want with a timestamp so it survives your sleep and comes back with an age attached. | Active |
