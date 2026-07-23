## function_count
_Last updated: 2026-07-24 07:24:50_

**GAP:** I want to see how much work is actually in a file without reading it all, and the only way I have right now is read it and count lines in my head. That's slow and I get it wrong.

**SHAPE:** Takes a path (file or folder) and returns a string: total functions found, broken down by file if it's a directory. Python files only, matching `def something(`. Returns "ERROR: ..." on bad paths instead of raising.

**TEST:** dir_shape.py has exactly one function named dir_shape. Running against it should say 1. A folder with two files, three defs total, should say 3 and name both files. Bad path errors.
