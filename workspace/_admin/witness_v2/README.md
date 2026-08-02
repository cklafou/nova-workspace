# MOVED — 2026-08-02
_Last updated: 2026-08-03 00:54:35_
This folder's contents live in `nova_body/nova_witness/` now (Cole: the witness is a body
part, so its engine, golden cases, harness, and reports belong in her body, not in _admin).

    python nova_body/nova_witness/extract_golden.py
    python nova_body/nova_witness/replay.py --endpoint http://127.0.0.1:8080 --cases nova_body/nova_witness/golden_seed.jsonl

Reports: `nova_body/nova_witness/reports/`. Nothing else remains here.
