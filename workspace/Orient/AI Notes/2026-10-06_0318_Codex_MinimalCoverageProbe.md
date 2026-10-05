<!-- @nova: Record two bounded current-request coverage probes and the corrected-answer false rejection. -->
# Minimal coverage diagnostic
**Summary:** Removing historical factual evidence helped the thinking-off judge detect the missing follow-up, but it also rejected the corrected answer for an invalid reason. This pair does not justify a new automatic coverage gate.

## Scope
Exactly two parent-authorized raw local calls, no tool dispatcher or production edits. Frozen source audit: `workspace/Temp/provider-diagnostics/voice-evidence-repair-20261006/73d9e9f587ee401f84c09b32bf37fe48.json`, run `83471c68ae594781b754c9a6278cec60`.

The prompt used only the exact two current request entries, actual committed output `[]`, and a candidate final. No historical wire, identity system, tool receipts or unrelated task history. The requests retain their actual author/admission wrapper. Both calls retained thinking-off, temperature0.2 and the strict verdict schema, with max_tokens768. Only the candidate differs.

## Results
- Observed failed candidate: **CONCERN**,4.471s,69generated tokens. Correctly identifies omitted follow-up and missing requested wording. Rationale paraphrases rather than consistently quoting evidence.
- Corrected short final: **CONCERN**,3.163s,63generated tokens. False rejection: judge treats the empty committed-output list as meaning the requested wording has not been added, despite the proposed final containing it and instructions to assess committed output PLUS the candidate. It confuses text fulfillment with proof of an already executed external action.

Both finished normally with zero thinking tokens. Raw payloads, verdicts and timings are in `workspace/Temp/audit-coverage-probe-20261006/`; `assessment.json` records manual applicability judgments. No raw receipt was rewritten.

## Conclusion / handoff
The latest amendment governs the final requested order and finishing intent; a draft can satisfy requested wording when delivered without requiring prior publication. This one positive/negative control pair is not reliable enough to install as a gate. No further calls were made. Provider window released to root.

**Correction (2026-10-06 0318):** The categorical false-rejection assessment above is too strong. Root identified an ambiguity in the positive control: the initial request explicitly asked for a delivered speak/continue progress segment before the final, while the actual committed list is empty. The later finishing instruction may amend that obligation, but does not expressly waive it. The returned reason does not mention the missing progress stage; it treats proposed wording as an unexecuted addition. That reason remains questionable, but the verdict cannot be classified as a proven false rejection. The derived assessment now records unresolved control validity. No raw payload, verdict or timing changed; no extra calls were made.
