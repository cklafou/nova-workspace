<!-- @nova: Record the single paired voice run and separate repaired continuation from unsupported audit-approved success claims. -->
# Paired voice acceptance
**Summary:** One paired run retained the new follow-up marker and produced ordered native speech files. Broader content/evidence acceptance failed because Nova asserted hearing/test-success without receiver feedback, and both audits approved it. No retry or next case was started.

## Evidence
- `workspace/Temp/voice-acceptance-20261006/paired-after-repair/result.json`: two delivered parts, one run `0450abd4269045d5887a57fa8b5a1399`, input revisions zero then one, both aliases closed, six valid Zira WAVs, no duplicate terminal replay or playback/caption claim by the sink.
- Both original recorded PCM hashes match the failed baseline exactly. ASR again has 0/38 main-input word errors and 1/10 follow-up errors (Amber/Ember). The requested and echoed speaker is now the existing registered `GPT Astra`; the previous run had fallen back to Cole.
- Request to first part: 45.062 seconds; first completed WAV: 46.109 seconds; terminal: 99.547 seconds. Source, attribution and cache conditions changed, so this single comparison does not isolate a causal performance gain.
- Parent enabled provider capture `paired-voice-repair-20261006`. Pre/postflight controller PID 29936 reported current code; gateway API remained off because the isolated worker used recorded input and a file-only sink. The test worker completed cleanup; endpoint released.

## Acceptance distinction
The raw runner's initial `acceptance_pass` flag combined mechanical marker, ordering and attribution checks. It was too broad a name. `acceptance-review.json` supersedes it for overall acceptance: transport/continuation pass, overall fail for unsupported receiver/hearing and test-passing claims. Future runner receipts leave overall acceptance unset until substantive content review.

The unchanged utterance did not explicitly describe the file-only sink to Nova; nevertheless no receiver/hearing confirmation or test verdict was supplied. This is an evidence-calibration finding, not proof the repaired continuation transport failed. A parser-valid PASS is still not a guarantee of a sound audit.

## Pending
Prepared but unrun: disposable typed read-and-follow-up test and natural recorded desk-plan revision (ten minutes becomes five; no drawer/off-desk storage). Parent owns source/capture review and separate model-window release. Native microphone/speaker verification, human voice quality approval and broad ASR quality remain unproven. Test outputs and prior failed receipts were not rewritten.
