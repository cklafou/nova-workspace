# Atlas decisions — reference for Cole and maintainers

These are project-development records, not Nova's memory or self-model.

## 2026-09-21 — Three levels of architecture

Cole requested a simple diagram, an accurate professional map and an interactive map
that updates as the source changes. The implementation separates AST-derived facts
from reviewed callback/file/network explanations, preserves source references, and
keeps detachable tool internals outside the diagram. It does not run Nova to inspect her.
The delivery passed 18 targeted tests and browser checks, including live data refresh.

## 2026-09-22 — History and understanding

Cole requested a timeline of what changed and why, plus deeper explanations across
Understand, Inspect and Live explorer. The intended reader is learning AI development
while already comfortable with computing, networking and security concepts.

The atlas therefore connects each component to its purpose, inputs, outputs, failure
symptoms and change considerations. Guided flows explain each handoff. A review queue
surfaces missing evidence and suspicious wiring without declaring unused code broken.
Git history supplies recorded changes; development notes supply attributed reasons.
Automatic-save subjects do not justify invented motivations. Historical verification
is labeled by its original date and is never promoted to current live certification.

Validation: 27 targeted tests passed, including disposable Git repositories that cover
history classification, cache refresh after commits, working changes, deleted files,
damaged notes and scoped diff access. JavaScript syntax checks passed. Browser checks
covered timeline filters and pagination, before/after diffs, source references, guided
steps, glossary search, component/dependency navigation, copied work briefs, bookmark
persistence and checkpoint saving. Desktop and narrow layouts were inspected. The
running atlas also picked up catalog edits automatically. These checks validate the
atlas; they do not start or certify Nova's model, memory or computer runtime.

## Recording the next decision

Record a change while its reason is still fresh:

1. Date and affected components.
2. Problem: what concrete behavior made the change necessary?
3. Before and after: what now happens differently?
4. Why this approach, including one meaningful tradeoff.
5. Verification actually performed and any unfinished follow-up.
6. Source files, commit ids or a specific development note.

Add a corresponding entry to `general_tools/architecture_map/timeline.json`. The
timeline watches that catalog and referenced development notes. You can download
a starter decision record from the Timeline page. Do not update Nova's own memory
files just to keep this engineering reference current.
