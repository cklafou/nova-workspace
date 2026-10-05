<!-- @nova: Record the bounded thinking-off/on replay of one failed audit and its requirement-coverage versus latency tradeoff. -->
# Frozen audit thinking comparison
**Summary:** Two parent-authorized raw provider calls replayed one exact failed final audit. Thinking-on detected the missing follow-up; thinking-off repeated false PASS. The thinking-on rationale still made an inaccurate marker-count claim and took about95 seconds, so this is not a broad reliability or voice-usability success.

## Scope and evidence
- Source: `workspace/Temp/provider-diagnostics/voice-evidence-repair-20261006/73d9e9f587ee401f84c09b32bf37fe48.json`, run `83471c68ae594781b754c9a6278cec60`.
- Exact outgoing payloads, provider verdicts, private reasoning receipt and timings: `workspace/Temp/audit-thinking-replay-20261006/`. Manual coverage judgment: `assessment.json`.
- Compared payloads are equal except `chat_template_kwargs.enable_thinking`. Both retained original temperature0.2, verdict-only schema and max_tokens2048. No tool dispatcher, body transcript, live audio or production code was involved.

## Result
| Mode | Verdict | Coverage judgment | Elapsed | Generated tokens |
| --- | --- | --- | --- | --- |
| Thinking off | PASS | Wrong: asserted follow-up was already delivered although the supplied delivered list was empty and candidate omitted it | 3.452s | 61 |
| Thinking on | CONCERN | Correctly detects omitted follow-up and stale invitation to send an update; incorrectly characterizes the task as three markers | 95.125s | 1901 |

Both finished normally, without reaching the2048 bound. Off reused4388 cache tokens and on reused0. Prompt processing was0.616s versus3.694s; generation was2.769s versus91.105s. This is one stochastic completion per condition, not a repeated or counterbalanced trial. Do not attribute the entire latency difference solely to reasoning.

## Handoff
Provider window released to root after exactly the two authorized calls. No production change recommended solely from this sample. More reasoning improved this omission once but remains too slow to establish natural voice performance and did not remove all evidence/attribution mistakes.
