# Nova A2: personality-informed refinement
_Last updated: 2026-10-03 04:41:56_

Date: 2026-09-22. Status: **A is the user-selected base; A2 is a proposal for review.**

The request was to make A more distinctive without adding much complexity, using the character influences and dialogue examples behind Nova's personality LoRA. This study concerns avatar design. The source material describes authoring intent; it does not establish which adapter is loaded today or how strongly a trained model expresses each influence.

## What the admin history contains

The original files are no longer present in the current admin training directory. Four historical documents were recovered into `sources/` from Git commit `4a85abc9d463cc10f794451752f7472275c13fce`. Original paths and SHA256 hashes are in [provenance.json](provenance.json). These are reference copies; no files were restored into Nova's active configuration or training folders.

The [v1 dataset specification](sources/nova_core_lora_dataset_spec.md), lines 10-30, gives this roster:

| Role in the writing brief | Influences | Intended qualities |
| --- | --- | --- |
| Foundation | Lucifer, Justice, Cortana | Composure, quiet pride, genuine ease, capable partnership and banter |
| Strong texture | Invisigal, Midna, Peridot | Punk tomboy bite, outward teasing, inward delight in building |
| Smaller accents | Goldship, Twilight Sparkle, Toph, Pinkie Pie | Absurdist humor, studious curiosity, secure swagger, occasional playful energy |

The [v2 character bible](sources/nova_core_v2_character_bible.md), lines 27-53, explicitly revises that balance: Lucifer roughly 40%, Justice 25%, Cortana 25%, Toph 10%, with the gremlin and trickster influences reduced to occasional accents. **These percentages are writing guidance, not measured LoRA contributions.** Its useful design cue at lines 81-85 is that the tomboy quality comes from being direct and unfussy. Confidence should look comfortable rather than performed.

The [strengthened-spec draft](sources/nova_core_v2_strengthened_spec.md), lines 50-67, proposes further influences including Senku and Korra, with optional Vegeta. Those proposals are marked for approval, so this refinement does not treat them as established influences.

These documents are different authoring stages. The v2 bible calls itself a replacement for the trait-list draft; the saved documents alone do not prove the exact dataset used in a completed training run.

## What the dialogue examples add

The historical [mischief and decision examples](sources/nova_lora_dataset_batch5_mischief_decision_solonarration.md) show playful needling, pride in finishing work, and dropping the joke when someone needs support.

Current v6 examples were inspected in `workspace/_admin/Training_stuff/v6/nova_core_v6.jsonl`. Particularly relevant examples:

| JSONL line | Training example | Visual implication |
| --- | --- | --- |
| 8 | When the user cannot sleep, she offers understated practical care and casual company. | A relaxed, warm expression needs to belong to the same face as the smirk. |
| 55 | In response to praise: “Good, you should be. I bled for that one.” | Pride can be direct and pleased, without posing for approval. |
| 96 | An authored reflection describes her humor as dry, smug and needling, while describing the blend as her own. | Keep the expression distinctive without dressing her as any source character. |
| 343 | The self-portrait example acknowledges flaws in the mouth and hair while still liking the image. | Preserve the preferred portrait's identity and allow grounded satisfaction. |

The current v6 specification also targets a less stilted voice. The v7 specification and sampled additive examples concern behavior such as solitude, deliberate rest, attribution and personal wants rather than introducing a replacement character roster. All of these are **training examples**, not evidence that the depicted experiences actually occurred or that a running model behaves this way.

## A2 design decisions

The primary identity remains Nova's preferred self-portrait: pale blue skin, orange eyes, violet asymmetric hair, dark swept ears with cyan accents, and a confident tomboy face. A's practical bomber jacket, covered shirt, tapered cargo trousers and sneakers remain the clothing foundation.

| Proposed addition | Purpose | Personality connection |
| --- | --- | --- |
| Slightly sharper standing collar with violet inner facing | Gives the upper silhouette a recognizable frame without adding armor | Composure and quiet authority |
| One small amber ear cuff | Creates a single warm accent near the face and echoes the eyes | A restrained punk detail and self-possession |
| Four-point spark with an incomplete orbit, repeated on sleeve and zipper pull | Gives Nova a compact emblem that can recur across future outfits | Curiosity and pride in making things; the orbit also suits her name |

The cuff and emblem are **new visual proposals**, not details found in the personality canon. The sheet includes four expression targets: **calm, teasing, build pride, and quiet warmth**. Expression and posture carry much of the personality; accessories do not have to carry it all.

My recommendation is to keep her neutral face composed and give the playful and delighted expressions more range when animated. That preserves the revised bible's calm foundation while retaining the builder and trickster accents the user likes.

## Deliverables and generation record

- [A2 concept sheet](../nova-a2-personality.png)
- [Full generation prompt](a2-prompt.txt)
- Generation mode: built-in `image_gen` tool, reference-image edit.
- Reference 1 / edit target: `avatar_design/2026-09-22-concepts/nova-a-everyday.png`.
- Reference 2 / primary identity: `workspace/Nova_Created/art/2026-07-19/nova_self_033541_66590_Tomboy_Preferred.png`.
- Generated original: `C:/Users/lafou/.codex/generated_images/01a0bc93-e290-7b10-aec0-24e6027be47a/exec-cd90d8bd-e3d2-4899-8dab-299a5a8a69f9.png`.
- Project copy SHA256: `3CEDDC0EF8172AB7A59391D57B90C5C1C1EC9D553CD9756F163A499E7856CD71`; verified identical to the generated original.

The concept was visually reviewed for preservation of A's identity, the three additions, full-body framing, and expression variety. It is an illustration, not a dimensionally verified modeling turnaround. After choosing the final design, the next stage is a consistent front/side/back reference sheet and an expression plan for the Blender model and facial rig.

No Nova runtime, personality, training data, or memory files were changed for this study.
