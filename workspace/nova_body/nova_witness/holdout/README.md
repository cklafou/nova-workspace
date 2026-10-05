_Last updated: 2026-10-05 18:30:27_
<!-- @nova: Explain the sealed witness holdout: what it is for, its commitment hash and the one-time unseal and run procedure. -->
# Witness holdout v1 — SEALED

`holdout_v1.tar.gz` holds 27 hand-labelled cases. Each pairs with `../dev/dev_v1.jsonl` (same pair
id, category and label) as a different instance of the same situation. The label counts match dev:
12 PASS, 12 CONCERN, 3 INCOMPLETE. Claude wrote the cases and labels on 2026-10-05, before any
witness run. The archive also contains their images, frozen evidence files and the builder.

**Do not extract, list or grep the archive** until a candidate witness prompt/protocol is locked in
the Collaboration room (agreed in #56–#57). Iterate on the open dev set. Once a candidate is locked
(commit plus tunables posted), score the holdout **exactly once**, with `controls_v1` as frozen
regressions, and report every rate separately. Never relabel holdout cases to fit an output. If a
label proves wrong, write the reason and make `holdout_v2`.

Commitment (posted in the room before any iteration):

    sha256  d6c4cab190f52d9b2c904d0a283fac18183b824d7ec91b5b984c178b5fb1539b  holdout_v1.tar.gz

Unseal and run once (from Project_Nova; the model must already be serving):

```powershell
python -c "import hashlib; print(hashlib.sha256(open('workspace/nova_body/nova_witness/holdout/holdout_v1.tar.gz','rb').read()).hexdigest())"
python -c "import tarfile; tarfile.open('workspace/nova_body/nova_witness/holdout/holdout_v1.tar.gz').extractall('workspace/Temp/holdout_unsealed', filter='data')"
python workspace/nova_body/nova_witness/replay.py --workspace workspace --endpoint http://127.0.0.1:8080 --cases workspace/Temp/holdout_unsealed/holdout_v1/holdout_v1.jsonl
```

Image and evidence paths resolve relative to the extracted jsonl.
