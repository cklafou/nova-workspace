<!-- @nova: Record disposable RunPod cleanup, removal of the completed pod and validation. -->
# Disposable training pods
**Summary:** Cole requested deletion after successful training so idle storage does not keep billing. The completed Qwen 3.8 pod and its attached 150 GB storage were deleted; future successful training runs do the same after local verification.

## Did
- `nova_updater/runpod.py`, `train.py`, `net.py`: stop GPU use, require every expected epoch plus complete six-file provenance, verify installed hashes, then DELETE the job pod and require GET 404 before declaring it gone. Clear only its matching saved pod ID. The next run creates a fresh nearby pod.
- Failure/cancellation or unverified outputs keep recoverable files and explicitly report ongoing storage costs. Delete failure retries stop and reports cleanup failed. Separate network volumes are not deleted; process death/provider failure remain cleanup limitations.
- Updated updater UI/paid notice/job summary and cache version; updated authored Orient, updater README and the model training README. No wallet cap or automatic recharge added.
- Real completed pod `ezt73ef3tpulbw`: both installed adapter hashes and six input/six runtime-detail checksums verified locally. DELETE returned 204, GET returned 404, pod list was empty. Saved pod ID cleared. Receipt: `models/Training Files/Qwen 3.8 27B Dense/nova_core_v7_qwen38_r2/Run Details/7e4c3f79ab5b/pod-cleanup.json`.
- Existing job histories now show confirmed deletion; the original 8765 API returned that updated status before the controller was closed externally. No native desktop or Nova process control was performed.

## Verified
- Updater suite: 173 tests, OK, 3 opt-in skips. Includes 15 cleanup boundary tests and 6 isolated HTTP deletion/error tests.
- Nova Chat updater integration: 8 tests passed. Node updater UI fixture passed. Compile and diff-whitespace checks passed.
- Orient refresh: zero pending reviews and zero dangling references; strict check follows this note.
- No additional paid training launched for testing. Future automatic cleanup verified in fixtures; current completed-pod deletion verified against the provider.

## Open / next
- Cleanup source loads on the next Nova Chat launch; the controller was offline at handoff, so the live collaboration post could not be delivered.
- Local finished adapters remain inactive pending Cole's runtime testing/A-B selection. Remote caches/checkpoints were discarded as requested; final local outputs and reproducibility records remain.
- This note supersedes the prior retained-volume/never-terminate guidance in earlier dated notes. Do not restore that old policy.
