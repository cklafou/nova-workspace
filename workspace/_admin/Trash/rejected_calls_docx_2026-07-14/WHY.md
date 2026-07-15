# Rejected — 2026-07-14
_Last updated: 2026-07-15 23:14:48_

A Word doc + PNG renderer for the call graph (calls_order_doc.py).

Cole's verdict, and he's right: "That is so bad for humans to read."

It rendered a node-and-arrow graph. Technically correct, colour-coded, layered by call depth —
and still a blob you have to decode. That is the SAME failure as leaving Mermaid source in a text
file, just wrapped in a heavier format and three extra pip dependencies.

The point of an orientation document is to answer a question FAST. If you have to study it, it has
failed, no matter how accurate it is. Do not rebuild this.

If a visual is ever wanted again: the useful thing is not a graph of every function. It is a short,
readable NARRATIVE of the few paths that matter ("Cole speaks -> ... -> tool runs -> receipt
written"), in plain language, in the .md. Accuracy was never the problem here. Legibility was.
