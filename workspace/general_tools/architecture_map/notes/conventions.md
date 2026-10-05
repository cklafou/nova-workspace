_Last updated: 2026-10-06 03:19:21_
---
doc: OPERATIONS.md
order: 5
---
<!-- @nova: Orient note: the file conventions every person and agent follows, published in OPERATIONS.md. -->
## File conventions

**Every file says what it is for in its first lines.** Add one line that starts with `@nova:`,
written in the file's own comment style:

| File | Purpose line |
|---|---|
| Python, PowerShell, shell, TOML, plain text | `# @nova: …` |
| `.cmd` / `.bat` | `REM @nova: …` |
| JavaScript | `// @nova: …` |
| CSS | `/* @nova: … */` |
| Markdown, HTML | `<!-- @nova: … -->` (invisible when rendered) |

Say what the file is *for* (its job, and who relies on it) in one sentence, and change the line
when the job changes. Orient reads it on every regeneration and uses it as the file's description
in [INDEX](INDEX.md); nothing is guessed from a filename. Files written before this rule fall back
to a Python docstring, a tool's `description`, or a Markdown title outside `nova_body/`. Files with
none of these are listed under [Files without a purpose line](INDEX.md#files-without-a-purpose-line).

Not covered: Nova's own records (`nova_body/SELF/`, `Tasking/`, `memory/`, `logs/` and her night
notes), which Orient lists but never quotes; backups; and formats without comments, such as JSON.
A generated file gets its purpose line from the code that writes it.
