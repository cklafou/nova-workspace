<!-- @nova: Record measured prompt-cache repair for conversational continuations and the remaining cross-turn context limitation. -->
# Provider cache diagnosis and repair
**Summary:** A controlled local provider experiment proved that the existing single-slot RAM cache restores Nova's long prompt after an inline audit. The measured zero-reuse continuation was caused by an unintended switch from conversational fast mode to thinking mode, whose selected model template changes the first system tokens.

## Did
- Coordinated a narrow `nova_body/nova_voice/nova.py` change, atomically applied by bridge while it owned that file: conversational `speak` segments and plain follow-ups no longer count as tool reasoning loops. `voice_fast` keeps its fast mode for those steps. An actual tool proposal/attempt, held premise, witness objection, or guard correction still enables deliberation. Input does not reset this flag or the total budgets. Other registers and the disabling tunable retain prior behavior.
- Added `nova_body/tests/test_voice_cache_mode.py`: six actual-body fake-provider cases checking provider kwargs, delivered segments, audit behavior and tool receipts.
- No provider binary, launcher flags, RAM/KV budget, reasoning instructions, witness policy, trust roles, or chat template was changed.

## Evidence
- Installed provider: b9733 / f449e0553, one slot, 65,536 context, 8,192 MiB RAM prompt cache. The original measured run retained both its ~1,594 MiB main prompt and ~768 MiB audit prompt; cache capacity was not exhausted.
- Captured first and second main requests had identical system/context and prior messages. The first disabled thinking; the second enabled it because `loop_counter > 1` also described a second spoken segment. The selected GGUF template prepends the xhigh reasoning instruction before the system when thinking is enabled, changing the shared prefix near token three.
- Root authorized and started the model-only probe; body/voice/autonomy remained off. Three direct local API calls used captured full message structures, with one generated token per call to isolate prefill; no tool dispatch, chat messages, audio or desktop control.
- Measured sequence: cold main 38,912 tokens / 31.812 s prefill; inline audit 5,098 tokens / 4.159 s; same-mode continuation 38,912 cached tokens plus 153 new tokens / **0.382 s prefill**, 1.268 s total request including cache restoration. This is a prefill test, not an audit-quality or spoken-latency certification.
- Receipt: `workspace/Temp/provider-cache-source/baseline-same-mode.json`; helper/source evidence in the same Temp directory. No private prompt text is duplicated in the receipt.
- GPU usage before/after: 4090 9,496→9,532 MiB; 3090 20,789→20,824 MiB. No extra slots or memory allocation configuration was introduced.

## Verified
- Six focused body tests passed: fast conversational segments, input during audit, genuine tool chain, witness correction, withheld tool proposal reconsideration, and unaffected normal register/tunable behavior.
- Selected model header only was inspected; weights were not loaded by inspection. Provider runtime was controlled by root, not this subagent.
- Existing source regressions and the newly integrated recovery work remain part of root's final combined test pass.

## Limits / next
- First cold prompt remains approximately 32 seconds in this measurement. A newly built turn changes clock/retrieval/body context in the system message, so cross-turn reuse is not established by the same-run result.
- Exact build source creates hybrid/recurrent checkpoints before the latest user input and near prompt end. `--ctx-checkpoints` (alias `--swa-checkpoints`) bounds retained checkpoint count; `--checkpoint-min-step` only sets minimum spacing. Neither is a periodic stable-prefix checkpoint knob. `--cache-reuse` requires shiftable memory and is not a general hybrid workaround.
- The actual `/apply-template` endpoint rejected a synthetic late system message with HTTP400. Cole's trusted body context was not relabelled as user data; no template override was installed.
- Primary source references: https://github.com/ggml-org/llama.cpp/blob/f449e0553/tools/server/server-context.cpp (slot/cache and checkpoint placement); https://github.com/ggml-org/llama.cpp/blob/f449e0553/tools/server/server-task.cpp (RAM prefix cache); https://github.com/ggml-org/llama.cpp/blob/f449e0553/tools/server/README.md (installed API/CLI contracts).

## For Codex / Claude
- This corrects the provisional hypothesis that audits necessarily evict the active prompt. They switch the active slot, but the provider's existing RAM cache restores the main prompt when its prefix matches.
- Root owns final live conversational validation and Orient explanations/review marks. Do not advertise natural voice latency as solved from this isolated prefill result.
