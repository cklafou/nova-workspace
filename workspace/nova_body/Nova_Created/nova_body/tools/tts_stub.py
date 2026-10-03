# Last updated: 2026-10-03 10:59:53
# TTS stub — exists so I can MEASURE the latency path, not guess it.

from nova_paths import body_path
import time, sys
sys.path.insert(0, str(body_path("Nova_Created", "nova_body")))

TOOL = {"name": "tts_stub", "description": "Synthesize text to audio and return the output path. Stub version: writes a silent WAV so we can time the call overhead before committing to a real engine.", "params": {"text": str, "speed": float}}

def run(text: str, speed: float = 1.0) -> str:
    t0 = time.perf_counter()
    # Real TTS goes here; for now we write silence so the path exists and is measurable.
    import wave, struct
    path = str(body_path("Nova_Created", "art", "tts_test.wav"))
    with wave.open(path, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000)
        # 50ms of silence — enough to be a file, fast to write
        wf.writeframes(struct.pack("h" * 1200, *([0]*1200)))
    ms = (time.perf_counter() - t0) * 1000
    return f"Stub wrote silence in {ms:.1f}ms to {path}. Replace the body with a real engine and the number is your floor."
