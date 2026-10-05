<!-- @nova: Record strict native audit JSON protocol, installed-provider format probes, and remaining semantic limitations. -->
# Audit protocol schema
**Summary:** The installed local provider supports grammar-constrained audit JSON. Added a pure body schema/classifier; bridge owns integration into witness.py and nova.py. Valid shape does not imply a correct factual ruling.

## Did
- Added `workspace/nova_body/nova_cortex/audit_protocol.py`: exact verdict objects with PASS/CONCERN/INCOMPLETE plus a nonblank reason; or one explicitly allowed read_file/list_dir/memory_search request with its real argument fields. Zero-read or forbidden-read schemas contain only verdicts.
- Added `workspace/nova_body/tests/test_audit_protocol.py`: whole-document parsing, duplicate keys, trailing prose, embedded tool JSON in verdict reasons, mixed shapes, unsupported tools/arguments, final-read prohibition, caller allowlist, independent schema copies. The helper does not accept legacy prose; witness's wrapper retains its existing strict legacy contract.
- All files written atomically. No Nova records, service state, microphone, speaker or desktop changes.

## Verified
- Six isolated protocol tests, compilation and scoped diff check pass.
- Four explicitly authorized short synthetic streaming requests to existing local port 8080, no actual tool dispatch. All HTTP 200 with valid JSON. Initial three format probes took 2.000, 1.244 and 2.279 seconds. The final per-tool schema took 2.031 seconds and returned the exact requested fixture read. Receipts: `workspace/Temp/audit-schema-probe/result.json` and `final-schema-result.json`.
- The zero-read probe returned INCOMPLETE for absent file contents. The greeting probe nevertheless invented an unnecessary file read; schema enforcement does not repair evidence judgment or task relevance. No end-to-end Nova behavioral improvement is claimed from these probes.

## Source contract
Installed llama.cpp b9733 / f449e0553 accepts response_format type json_schema with json_schema.schema. Its grammar constrains output but is not itself inserted into the prompt, so bridge must update conflicting prose-format instructions. Generic additionalProperties may admit invalid keys on this build; the production helper enumerates each tool's arguments instead.

Primary references: [exact-build server converter](https://github.com/ggml-org/llama.cpp/blob/f449e0553/tools/server/server-common.cpp) and [grammar/schema documentation](https://github.com/ggml-org/llama.cpp/blob/f449e0553/grammars/README.md).

## Handoff
Bridge has the optional fetch response_format argument and helper API. No unconstrained retry on schema failure is recommended: errors/truncation remain visibly unapproved. Root owns source fingerprint/Orient updates and subsequent integration/voice acceptance. Provider window was released after the fourth probe; no more inference from this reviewer.
