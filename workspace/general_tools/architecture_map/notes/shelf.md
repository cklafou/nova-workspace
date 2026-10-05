_Last updated: 2026-10-05 21:27:02_
---
doc: ARCHITECTURE.md
order: 10
---
<!-- @nova: Orient note: introduces Nova's own tools above their derived table, published in ARCHITECTURE.md. -->
## Nova's shelf

Tools Nova wrote for herself live in `nova_body/Nova_Created/`: `nova_body/tools/` for pluck-safe
tools and `general_tools/tools/` for tools that need the face, with tests beside them in `tests/`.
Each exposes `TOOL = {name, description, params, version}` and `run(**args) -> str`, and `nova_forge`
discovers them. This table is generated from the files themselves, so she no longer has to keep it
by hand. A test file existing is not evidence that it passes.

{{SHELF_TABLE}}
