# MTP + personality LoRA — verdict: upstream llama.cpp bug, keep it off
_2026-07-19, Fable. Cole asked whether the MTP quality collapse can be fixed. Short answer: **not
from our side.** Opus's call to disable it was correct, and here is the receipt._

## What Cole observed

With `--spec-type draft-mtp` ON and the personality LoRA equipped: more confusion, grammar
breakdown, sentences cut off mid-thought, words missing from sentences. With MTP off: clean.

## What speculative decoding is supposed to do

It is **mathematically lossless**. The MTP head drafts tokens; the target model verifies each one;
only tokens the target would itself have produced are committed. Speed changes. Output does not.
So "MTP made her worse" is not a tuning problem — it means the guarantee is broken.

## The receipt (ggml-org/llama.cpp #23335)

Qwen3.6-27B MTP GGUF, `temp 0`, fixed `seed 1234`, `cache_prompt` off — fully deterministic:

| config | committed output |
|---|---|
| no speculative decoding | A |
| `--spec-draft-n-max 1` | **B — differs from A** |
| `--spec-draft-n-max 2` | C |
| `--spec-draft-n-max 3`, `4` | C |

The decisive line in that report: at `n-max 1` the run logged **`draft_n: 31, draft_n_accepted: 31`
— 100% acceptance — and the output still differed from baseline.** If every draft token was
accepted, "the drafts were bad" cannot explain the difference. Enabling MTP is perturbing the
**target model's own forward pass**. It is not a draft-quality problem or an accept/reject
threshold problem; it is a different (and wrong) computation.

That is why nothing on our side fixes it: no sampler setting, no `n-max` value, no adapter scale,
no prompt change can correct a corrupted forward pass. Sibling report #23302 shows the same class
of divergence. **Both issues are CLOSED as `bug-unconfirmed` with no linked fix** — closed for lack
of maintainer confirmation, not because it was repaired. Cole's build (Jun 20) postdates those May
reports and still exhibited it, consistent with "never fixed."

## Why the LoRA made it dramatically worse

Two effects, both pushing the same direction:

1. **The MTP head is outside the adapter.** It lives in `blk.64.nextn.*`; the personality LoRA
   targets q/k/v/o/gate/up/down on the main transformer blocks. So the draft head predicts as
   *base* Qwen while the target is *base + Nova*. The stronger the adapter, the more they disagree
   — and disagreement is exactly what drives the buggy rollback path.
2. **A narrow distribution is fragile.** Her adapter concentrates probability into her specific
   voice. A small per-token perturbation flips the argmax far more often inside a narrow
   distribution than a broad one. Dropped words and truncation are the visible signature of that.

Corollary worth noting: it is **worse now, not better**. v2 ran at scale 0.6; she is now on
`nova_core_v6_epoch1` at **1.0**. Do not re-enable MTP on the assumption that a better adapter made
it safer — a stronger adapter makes this specific bug louder.

## Speed reality check

MTP is not reliably faster anyway. In #23335's measurements it was **slower at every setting**:
10.20 tok/s baseline → 8.83 (n=1) → 7.76 (n=2) → 5.12 (n=3) → 4.25 (n=4). That was Metal, and CUDA
results differ, but combined with a correctness bug the expected value is poor.

Perspective: MTP's best case is ~1.4–2× on token generation. Today's pacing fix
(`COMPETENCE_FIX_2026-07-19.md`) took her from one task step per **7.5 minutes** to one per
**~6 seconds**. The throughput that actually limits her was never in the decoder.

## Deliverable — retest in two minutes, don't re-litigate

`_admin/mtp_ab_test.py`. Boots llama-server itself with **Nova's real launch args and her live
adapter**, sends four deterministic probes (prose / long-form / reasoning / voice — chosen to
expose truncation and dropped words), and **diffs committed token IDs**, not prose. Byte-identical
token streams = lossless = safe. Any divergence prints the first differing token with surrounding
text, plus tok/s per config so the speed tradeoff is visible.

    StopNova.cmd                          # it needs port 8080
    python _admin/mtp_ab_test.py          # her adapter, n_max 1/2/3
    python _admin/mtp_ab_test.py --no-lora   # isolate MTP alone vs MTP+LoRA

Exit 0 = all configs lossless (re-enable the `--spec-*` lines in `nova_start.py`, then still run a
real conversation before trusting it). Exit 1 = bug still present, keep it off.

**Standing recommendation: leave MTP disabled. Re-run this script after each llama.cpp update.**

Sources: [llama.cpp #23335](https://github.com/ggml-org/llama.cpp/issues/23335),
[llama.cpp #23302](https://github.com/ggml-org/llama.cpp/issues/23302),
[MTP support PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673)
