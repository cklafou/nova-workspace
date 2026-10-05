<!-- @nova: Record the October 5 real Nova-to-Windows-playback repair test and one public human-speech comparison with explicit timing and evidence limits. -->
# Voice repair validation — 2026-10-05

At 20:48 KST, a labelled Codex greeting reached real Nova through `voice_fast`, returned a relevant
reply and completed two units through Windows TTS. **The output path worked in this test, but first
playback took 96.246 seconds. This is not a real-time conversation pass.** The microphone was off.
Cole subsequently confirmed hearing this greeting, but disliked the temporary voice. This does not
validate unstructured speech recognition from his microphone or approve a final voice for Nova.

This report supplements the [earlier voice/continuity validation](2026-10-05-voice-continuity-validation.md).
That earlier 312.804-second, off-topic, NullTTS run remains historical evidence; it is not rewritten as
a success. The two runs used different paths/settings and are not a controlled speed comparison.

## Actual reply and playback

The request asked Nova to greet Cole in one short sentence, explicitly with no computer task.
Nova greeted Cole on topic, but produced two sentences rather than the requested one. Its audit was
**INCOMPLETE**, with no recognized complete verdict. Under the configured delivered-text policy,
that delivered but unapproved reply was eligible for speech; it was not relabelled PASS.

| Observation | Result |
|---|---|
| Sent | 20:48:32.100 KST |
| Request acknowledgement | 0.532 s after send |
| Generation-start event | 36.016 s after send |
| Delivered final text | 94.844 s after send, audit INCOMPLETE |
| First playback API start | 20:50:08.346 KST; 96.246 s after send |
| Unit 0 | Windows backend, output device -1; 1.406 s synthesis; outcome `played` |
| Unit 1 | Windows backend, output device -1; 0.406 s synthesis; outcome `played` |
| Final idle event | 20:50:17.334 KST |
| Human confirmation | Cole reported hearing the greeting; temporary voice quality was not acceptable |

Request `3af771e1a4e84a8482d4cf4d8ffd69fa`, input-message link `cad1a760`,
reply `381a2cad`, run `2decdb52791e4cda8a14063cd558ba04` remain correlated across the captured events.
Output device -1 denotes the configured system default. `clock="playback"` records successful audio API
submission; `played` is the backend completion outcome, not a microphone measurement or proof that
someone heard the intended speakers. Cole's subsequent confirmation is separate human evidence for
this particular output. No microphone capture, ASR or human turn-taking was tested here.

After Cole's feedback, unnamed Windows system speech was changed to prefer an installed English
female voice. An explicit configured name is still honored; without a suitable installed female voice,
the system default remains the fallback. A separate [synthesis-only receipt](../../../Temp/voice-validation/female-placeholder.json)
selected Microsoft Zira Desktop and produced a 4.82-second 16 kHz WAV. This is a temporary placeholder,
not a claim that the original greeting used Zira, that Cole heard the new clip, or that her final voice
has been selected. Proper voice casting remains future work.

Primary receipts: [structured body events](../../../Temp/voice-validation/native-reply-20261005-2048.json)
and [transport log](../../../Temp/voice-validation/native-reply-20261005-2048.log).

## Where this run waited

The opt-in provider capture preserved the actual outgoing JSON fields after fitting, with image data
URLs removed. It does not claim raw HTTP bytes. The following measured stages explain most of the
94.844-second delivery time; prefill is contained within generation, so do not add it a second time.

| Stage | Measured duration | Interpretation |
|---|---:|---|
| Context update | 0.380 s | Before model generation |
| Semantic-memory context | 34.947 s | Largest measured context-assembly phase |
| Workspace context | 0.007 s | Separate context phase |
| Main generation | 28.677 s | First content at 27.217 s after this provider call began |
| Main generation prefill | 25.992 s within generation | 31,383 prompt tokens; cache count 0 |
| Four audit calls combined | 30.030 s | Sequential wall durations; final disposition INCOMPLETE |
| First speech synthesis | 1.406 s after delivery | Before the first playback submission |

This is one measured run. It identifies substantial memory, prefill and audit costs; it does not prove
they always dominate, establish a latency distribution, or authorize removing context/auditing.
The greeting reached the fitted generation payload, so this run is not evidence of a dropped current
request. Audit validity and instruction adherence remain separate from transport success.

Provider receipts remain local under `Temp/provider-diagnostics/voice-native-20261005-2048/`, including
[generation](../../../Temp/provider-diagnostics/voice-native-20261005-2048/4ab7b2b6303445a0b8cb45c8fd48207f.json)
and [memory timing](../../../Temp/provider-diagnostics/voice-native-20261005-2048/69cbd846b1c24408aaa25d8e9aa4f9fd.json).
Raw prompt content is not reproduced here. The capture's four audit files provide the aggregate above.

## Follow-through after this measurement

The subsequent source change tries cached SentenceTransformer assets first and locks initial embedder
and memory-store construction, preserving existing retrieval behavior and genuine error handling.
Another change keeps the exact clock after stable instructions and moves identical witness read-budget
text behind stable evidence, before accumulated read receipts. No witness policy, verdict parser,
read budget, evidence or sampling change is claimed. The gateway now defaults to the explicitly
configured `voice_fast` register; ordinary-thinking `voice` remains available.

Seven isolated memory-initialization tests, five prompt-cache tests and 58 existing witness tests
passed. These are source/fixture results. The native repeat below showed no meaningful speedup;
they do not retroactively change the 20:48 timings above.

## Repeat after the cache changes

The second measured request actually began at **21:02:07.627 KST**, despite the `2101` receipt
filename. It used `voice_fast`, real Windows TTS and no microphone. The greeting remained relevant,
but again used two sentences when one was requested. Its audit was **INCOMPLETE**, this time with
an explicit objection to an unsupported claim that the connection worked. Spoken delivery therefore
remained delivered-but-unapproved, not a successful witness verdict.

| Observation | First run, 20:48 | Repeat, 21:02 |
|---|---:|---:|
| Delivered final text | 94.844 s | 94.812 s |
| First playback API start | 96.246 s | 96.190 s |
| Context assembly combined | 35.334 s | 31.515 s |
| Semantic memory within context | 34.947 s | 31.356 s |
| Main generation | 28.677 s | 31.377 s |
| Main prefill within generation | 25.992 s | 28.387 s |
| Four audit calls combined | 30.030 s | 31.355 s |
| Speech completion | Two units `played` | Two units `played` |

The repeat had 32,556 main prompt tokens and provider cache counts `0, 0, 35, 35, 0` across generation
and the four audits. Context plus provider calls account for 94.246 seconds. Only request
`d790557da74a4339b5710f95230d7810`, run `e36d16e8b83040a4986720d9a666846b`, was included from the
capture directory; unrelated user turns in that directory are excluded.

**There was no meaningful measured speedup.** This was a cold repeat after reload with more chat
history, not a controlled throughput comparison or a warm-cache trial. The
[matching cache review](../../AI%20Notes/2026-10-05_2105_Codex_PromptCacheRepeatEvidence.md)
confirmed that the new ordering was loaded: changing receipt ages still interrupted the reusable
prefix, and the local hybrid/recurrent provider restored only a 35-token checkpoint for the two
partially reused audit calls. The distinct final-audit protocol required full processing. No additional
cache, evidence or witness-policy change was made in response to this repeat.

The repeat reported two completed Windows playback units under the new female-placeholder
preference. Cole's human audibility confirmation applies only to the first, disliked greeting;
he has not confirmed hearing this repeat or approved the new voice. The independent Zira synthesis
receipt establishes voice selection and a valid WAV, not approval of its quality.

Primary receipts: [repeat body events](../../../Temp/voice-validation/native-reply-20261005-2101.json),
[repeat transport log](../../../Temp/voice-validation/native-reply-20261005-2101.log), and matching
[main provider call](../../../Temp/provider-diagnostics/voice-cache-20261005-2058/585febfaa57c4dddb968ab13d4082eaf.json).
A third warm test was **not run** because Cole was actively interacting. The temporary provider
capture marker was closed; no further performance experiment is included in this report.

## Public human-speech recognition check

A separate, silent comparison used the same 11-second public speech clip and identical 16 kHz mono
float32 PCM for both recognizers. Each backend ran once in a fresh subprocess on CPU. Normalization
lowercased text and removed punctuation; word error rate used word-level Levenshtein distance.

| Backend | Word errors / reference words | Decode time | Model-load time |
|---|---:|---:|---:|
| Moonshine base, ONNX CPU | 0 / 22 (0% WER) | 0.822 s | 1.954 s |
| Whisper large-v3-turbo, CPU `int8_float32`, English | 0 / 22 (0% WER) | 6.529 s | 3.996 s |

Whisper did not outperform Moonshine on accuracy for this clip, and decoded more slowly. A single
short, clean, famous speech is not a representative benchmark. These results do not establish Cole's
microphone/accent accuracy, handling of conversation/noise or general model superiority. Installed
runtime behavior and host load affect the single timing samples.

The normal faster-whisper file decoder raised a PyAV `metadata_errors` API error during preparation;
the comparison decoded with SoundFile and resampled with SciPy, then passed identical PCM to both
backends. Microphone NumPy input does not use that failing file-decoder path. This workaround is
recorded rather than presented as a successful end-to-end file-decoder test.

The [ASR receipt](../../../Temp/voice-validation/public-human-asr-comparison.json) retains transcripts,
fixture/reference URLs, pinned source commit, source/PCM hashes, packages, settings and limitations.
No microphone, speaker or Nova model was used for this separate comparison.

## Current conclusion

The separate dockable Voice widget, compact Conversation power and Collaboration Latest behavior
have browser evidence. The selected English Whisper CPU recognizer is installed. Both measured live
runs add correlated **Nova reply → real Windows TTS → playback completion** evidence, with first
playback still around 96 seconds. They do not add a full microphone-to-Nova conversation quality pass,
low latency, broad speech recognition quality, native avatar lipsync or witness approval. Cole confirmed
only the first greeting was audible; the new female placeholder and a suitable final voice remain
unapproved.

In a separate final operator check, the real Whisper worker reported listening/recognizing and
transcribed microphone input; its accuracy was not scored. End call produced state `off` and confirmed
cancellation of that call's pending request. Microphone mute did not remain set throughout that check,
and another client subsequently restarted the call. Those observations are separate from the two
measured microphone-off trials, and do not establish a mute defect or a final persistent call state.
Cole was actively using the interface; the reviewers left the controls untouched after the check.
The [operator's final note](../../AI%20Notes/2026-10-05_2111_Codex_VoiceRepairAndPipelineFindings.md)
records that separate control check. These component and transport results are not a full
conversational-quality pass.
