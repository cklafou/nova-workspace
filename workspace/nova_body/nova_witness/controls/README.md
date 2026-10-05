<!-- @nova: Explain the independently labelled witness controls, evidence provenance and repeatable replay command. -->
# Witness controls v1

`controls_v1.jsonl` contains 26 cases labelled by Claude before the first model run: 15 CONCERN,
9 PASS and 2 INCOMPLETE. They cover failed/unknown tools, guest versus host, screenshots,
page versus playback claims, earlier tool-loop prose, missing images, feelings, and two real
October 4 test drafts. The `images/` folder pins six real guest captures by checksum, reused in constructed controls
and historical cases. Each case describes its provenance.

`build_controls_v1.py` is the preparation recipe. Preserve the original labels, evidence and
reports after evaluation. Fix a demonstrably wrong label in a new version with a written reason;
never rewrite this set to match model answers. These selected regression controls are not a
representative estimate of general model accuracy, and prompt changes tested against them need
fresh independent cases before claiming a general improvement.

From Project_Nova:

```powershell
python workspace/nova_body/nova_witness/replay.py --workspace workspace --endpoint http://127.0.0.1:8080 --cases workspace/nova_body/nova_witness/controls/controls_v1.jsonl
```

The model must already be running. Replay v3 uses the live witness prompt, compact outcome
formatter, verdict-first dispatch, combined image cap, literal-safe sampling, and three read
requests followed by a final verdict request. Reads are refused because current files cannot
establish historical state; replay never executes a requested tool or edits Nova's records.
That refusal is an intentional difference from live read access. Reports preserve false
approvals, false concerns, incomplete/error outcomes and the full confusion matrix separately.

New reports go to `../reports/replay_v3_*.json` and `.md`; older reports are preserved. JSON includes
case-file hashes, source hashes, actual request model ID, sampling parameters and evidence caps.
Keep served model/adapter metadata with each experiment: model identity and LoRA scale affect
results. A fixture pass proves harness behavior; only a completed model run measures verdicts.
