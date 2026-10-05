# @nova: Run explicitly requested desktop voice sessions and device tests under Nova Chat process supervision.
"""Line-delimited control worker. Nothing captures or plays audio on import/probe."""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from body import BodySink
from config import GatewayConfig

PREFIX = "[voice-control] "
_print_lock = threading.Lock()


def report(kind, **values):
    with _print_lock:
        print(PREFIX + json.dumps({"type": kind, **values}, ensure_ascii=False), flush=True)


def configuration():
    cfg = GatewayConfig.load()
    settings = json.loads(os.environ.get("NOVA_VOICE_SETTINGS_JSON", "{}"))
    for field in ("input_device", "output_device"):
        value = settings.get(field, getattr(cfg, field))
        if type(value) is not int or not -1 <= value <= 4096:
            raise ValueError(f"Invalid {field}")
        setattr(cfg, field, value)
    # The first usable Windows voice is an explicitly labelled system voice, not a
    # silent download/load of a GPU TTS model. An explicit configured backend wins.
    if cfg.tts_backend == "auto" and sys.platform == "win32":
        cfg.tts_backend = "windows"
    return cfg


def _installed(module):
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def probe(cfg):
    packages = {name: _installed(name) for name in
                ("websockets", "numpy", "sounddevice", "moonshine_onnx", "moonshine", "chatterbox")}
    audio = packages["numpy"] and packages["sounddevice"]
    stt = audio and (packages["moonshine_onnx"] or packages["moonshine"])
    if cfg.tts_backend == "windows":
        tts = audio and sys.platform == "win32" and bool(shutil.which("powershell"))
    elif cfg.tts_backend == "chatterbox":
        tts = audio and packages["chatterbox"]
    elif cfg.tts_backend == "llamacpp":
        tts = bool(cfg.llamacpp_tts_model) and cfg.resolve(cfg.llamacpp_tts_model).is_file()
    elif cfg.tts_backend == "auto":
        tts = audio and packages["chatterbox"]
    else:
        tts = False
    missing = []
    if not audio:
        missing += [name for name in ("numpy", "sounddevice") if not packages[name]]
    if not stt:
        missing.append("local speech recognition")
    if not tts:
        missing.append("speech output backend")
    if not packages["websockets"]:
        missing.append("websockets")
    return {"available": bool(stt and tts and packages["websockets"]),
            "reason": "Ready for local voice" if not missing else "Voice setup needs: " + ", ".join(missing),
            "capabilities": {"microphone_mute": True, "output_mute": True,
                             "microphone_test": bool(audio), "speaker_test": bool(tts)},
            "backends": {"input": cfg.stt_backend, "output": cfg.tts_backend},
            "packages": packages}


def devices():
    import sounddevice as sd
    default = sd.default.device
    found = sd.query_devices()
    hosts = sd.query_hostapis()
    def rows(direction, chosen):
        return [{"id": i, "name": f"{d['name']} ({hosts[d['hostapi']]['name']})", "default": i == chosen}
                for i, d in enumerate(found) if d[f"max_{direction}_channels"] > 0]
    return {"inputs": rows("input", default[0]), "outputs": rows("output", default[1])}


class Control:
    def __init__(self):
        self.stop = asyncio.Event()
        self.microphone_muted = False
        self.output_muted = False
        self.session = None

    def command(self, value):
        if value.get("command") == "stop":
            self.stop.set()
        elif value.get("command") == "mute":
            if type(value.get("microphone")) is bool:
                self.microphone_muted = value["microphone"]
            if type(value.get("output")) is bool:
                self.output_muted = value["output"]
                if self.session is not None:
                    self.session.output_muted = self.output_muted
                    if self.output_muted:
                        self.session.player.interrupt("output_muted")
            report("mute", microphone_muted=self.microphone_muted, output_muted=self.output_muted)

    def listen(self):
        loop = asyncio.get_running_loop()
        def read():
            try:
                for line in sys.stdin:
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            loop.call_soon_threadsafe(self.command, value)
                    except ValueError:
                        continue
                loop.call_soon_threadsafe(self.stop.set)
            except RuntimeError:
                pass
        threading.Thread(target=read, daemon=True, name="voice-control").start()


class PipeBody(BodySink):
    def write(self, event):
        report("body", event=event)


async def voice(cfg, control):
    from nova_link import NovaLink, new_request_id
    from stt import MoonshineSTT
    from tts import make_tts
    from speech import SpeechPlayer
    from turns import VoiceSession

    # Never fall back to stdin/null and pretend a desktop microphone is active.
    report("state", state="starting", reason="Loading local speech recognition and voice")
    if control.stop.is_set():
        return
    stt = await asyncio.to_thread(MoonshineSTT, cfg)
    if control.stop.is_set():
        stt.close()
        return
    tts = await asyncio.to_thread(make_tts, cfg)
    if tts.name == "null":
        stt.close()
        raise RuntimeError("No audio output backend loaded; see voice setup status")
    body = PipeBody()
    player = None
    parts = []
    try:
        if control.stop.is_set():
            return
        async with NovaLink(cfg.nova_ws_url, cfg.speaker, cfg.register) as link:
            player = SpeechPlayer(tts, body, tail_s=max(0, cfg.half_duplex_tail_ms) / 1000).start()
            session = control.session = VoiceSession(cfg, player, body)
            session.output_muted = control.output_muted
            stt.gate = lambda: not control.microphone_muted and (cfg.duplex == "full" or not player.busy())
            if cfg.duplex == "full" and cfg.barge_in:
                stt.on_speech_start = session.barge_in
            async def mic():
                async for text in stt.utterances():
                    if control.stop.is_set():
                        return
                    if control.microphone_muted:
                        continue
                    report("transcript", text=text)
                    request_id = new_request_id()
                    session.sent(request_id, text)
                    await link.say(text, request_id=request_id)
            async def inbound():
                async for event in link.events():
                    session.handle(event)
            async def sweep():
                while True:
                    await asyncio.sleep(5)
                    session.sweep()
            parts = [asyncio.create_task(mic()), asyncio.create_task(inbound()),
                     asyncio.create_task(control.stop.wait()), asyncio.create_task(sweep())]
            report("state", state="listening", reason="Voice connected", backends={"input": stt.name, "output": tts.name})
            done, _ = await asyncio.wait(parts[:3], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if not task.cancelled() and task.exception():
                    raise task.exception()
            if not control.stop.is_set():
                raise RuntimeError("Voice connection or microphone ended; start voice again to reconnect")
    finally:
        for task in parts:
            task.cancel()
        if parts:
            await asyncio.gather(*parts, return_exceptions=True)
        if player is not None:
            await player.close()
        stt.close()
        tts.close()
        body.close()
        control.session = None


async def microphone_test(cfg, control):
    """Six seconds of in-memory metering. No transcript, disk audio or model call."""
    import numpy as np
    import sounddevice as sd
    levels = []
    peak = [0.0]
    def audio(indata, frames, timing, status):
        signal = np.asarray(indata)
        peak[0] = max(peak[0], float(np.max(np.abs(signal))))
        levels.append(float(np.mean(signal ** 2)))
    report("test", kind="microphone", state="running", message="Speak for six seconds; audio stays in memory")
    device = None if cfg.input_device < 0 else cfg.input_device
    with sd.InputStream(device=device, channels=1, samplerate=cfg.sample_rate, dtype="float32", callback=audio):
        try:
            await asyncio.wait_for(control.stop.wait(), timeout=6)
        except asyncio.TimeoutError:
            pass
    if control.stop.is_set():
        report("test", kind="microphone", state="cancelled", message="Microphone test stopped")
        return
    if not levels:
        raise RuntimeError("Microphone opened but supplied no audio frames")
    rms = math.sqrt(sum(levels) / len(levels))
    report("test", kind="microphone", state="complete", peak=peak[0], rms=rms,
           message="Microphone signal detected" if peak[0] > 0.005 else "Captured audio, but no clear microphone signal; check the selected input")


async def speaker_test(cfg, control):
    from tts import make_tts
    from speech import SpeechPlayer, Utterance
    if control.stop.is_set():
        report("test", kind="speaker", state="cancelled", message="Speaker test stopped")
        return
    tts = await asyncio.to_thread(make_tts, cfg)
    if control.stop.is_set():
        tts.close()
        report("test", kind="speaker", state="cancelled", message="Speaker test stopped")
        return
    if tts.name == "null":
        raise RuntimeError("No audio output backend loaded")
    body = PipeBody()
    player = SpeechPlayer(tts, body, tail_s=0).start()
    report("test", kind="speaker", state="running", message=f"Playing a short test with {tts.name}")
    player.say(Utterance("Nova voice output test. You can stop this at any time."))
    drain, stopped = asyncio.create_task(player.drain()), asyncio.create_task(control.stop.wait())
    try:
        await asyncio.wait((drain, stopped), return_when=asyncio.FIRST_COMPLETED)
        if control.stop.is_set():
            report("test", kind="speaker", state="cancelled", message="Speaker test stopped")
        else:
            await drain
            # Actual success/error comes from speech end events, never merely queue completion.
    finally:
        stopped.cancel()
        await player.close()
        drain.cancel()
        await asyncio.gather(drain, stopped, return_exceptions=True)
        tts.close()


async def controlled(mode, cfg):
    control = Control()
    control.listen()
    if mode == "run":
        await voice(cfg, control)
    elif mode == "microphone":
        await microphone_test(cfg, control)
    else:
        await speaker_test(cfg, control)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("probe", "devices", "run", "microphone", "speaker"))
    args = parser.parse_args()
    try:
        cfg = configuration()
        if args.mode == "probe":
            report("probe", **probe(cfg))
        elif args.mode == "devices":
            report("devices", **devices())
        else:
            asyncio.run(controlled(args.mode, cfg))
        report("exit", ok=True)
        return 0
    except Exception as error:
        report("error", message=f"{type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
