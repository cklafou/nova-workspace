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


def report(event_type, **values):
    with _print_lock:
        print(PREFIX + json.dumps({"type": event_type, **values}, ensure_ascii=False), flush=True)


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
                ("websockets", "numpy", "sounddevice", "moonshine_onnx", "faster_whisper", "chatterbox")}
    audio = packages["numpy"] and packages["sounddevice"]
    from stt import local_asset_status
    assets = local_asset_status(cfg)
    recognizer = str(cfg.stt_backend).lower()
    recognizer_module = {"moonshine": "moonshine_onnx", "faster_whisper": "faster_whisper"}.get(recognizer)
    stt = audio and bool(recognizer_module and packages[recognizer_module]) and assets["ready"]
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
        missing.append("local speech recognition" if assets["ready"] else
                       "local speech assets (run setup_windows.py --assets-only)")
    if not tts:
        missing.append("speech output backend")
    if not packages["websockets"]:
        missing.append("websockets")
    return {"available": bool(stt and tts and packages["websockets"]),
            "reason": "Ready for local voice" if not missing else "Voice setup needs: " + ", ".join(missing),
            "capabilities": {"microphone_mute": True, "output_mute": True,
                             "microphone_test": bool(audio), "speaker_test": bool(tts)},
            "backends": {"input": cfg.stt_backend, "input_label": assets.get("label", cfg.stt_backend),
                         "output": cfg.tts_backend, "vad": cfg.vad_backend},
            "assets": assets, "packages": packages}


def devices():
    """Offer only devices supporting this baseline's 16 kHz mono streams; no capture/playback."""
    import sounddevice as sd
    default = sd.default.device
    found = sd.query_devices()
    hosts = sd.query_hostapis()
    excluded = []
    def rows(direction, chosen):
        result = []
        check = sd.check_input_settings if direction == "input" else sd.check_output_settings
        for i, device in enumerate(found):
            if not device[f"max_{direction}_channels"]:
                continue
            name = f"{device['name']} ({hosts[device['hostapi']]['name']})"
            try:
                check(device=i, samplerate=16000, channels=1,
                      dtype="int16" if direction == "input" else "float32")
            except Exception:
                excluded.append({"id": i, "name": name, "direction": direction,
                                 "reason": "Does not support the baseline 16 kHz mono stream"})
                continue
            result.append({"id": i, "name": name, "default": i == chosen})
        return result
    return {"inputs": rows("input", default[0]), "outputs": rows("output", default[1]),
            "excluded": excluded, "sample_rate": 16000}


def _control_lines(stream):
    """Read Windows control pipes without holding a CRT stdin lock during native imports.

    A blocked TextIOWrapper/FileIO stdin read can hold the Windows CRT descriptor lock.
    NumPy's DLL initialization then stalled until a command arrived. Polling the native
    pipe avoids a pending blocking read while retaining the same newline-JSON protocol.
    """
    if sys.platform != "win32" or stream.isatty():
        yield from stream
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    read = kernel.ReadFile
    read.argtypes = (wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                     ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
    read.restype = wintypes.BOOL
    peek = kernel.PeekNamedPipe
    peek.argtypes = (wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
                     ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
    peek.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(stream.fileno())
    buffer = ctypes.create_string_buffer(4096)
    count = wintypes.DWORD()
    available = wintypes.DWORD()
    pending = b""
    while True:
        # Even a pending native blocking read reproduced DLL-import stalls on this
        # host. Peek + a short sleep keeps the control thread out of blocking I/O;
        # ReadFile runs only for bytes already present in our single-reader pipe.
        if not peek(handle, None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (38, 109):
                break
            raise OSError(error, "Could not inspect voice control pipe")
        if not available.value:
            time.sleep(0.025)
            continue
        if not read(handle, buffer, min(len(buffer), available.value), ctypes.byref(count), None):
            error = ctypes.get_last_error()
            if error in (38, 109):           # EOF / broken pipe: parent ended control
                break
            raise OSError(error, "Could not read voice control pipe")
        if not count.value:
            break
        pending += buffer.raw[:count.value]
        if len(pending) > 65536:
            raise ValueError("Voice control command exceeded 64 KiB")
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            yield line.decode("utf-8")
    if pending.strip():
        yield pending.decode("utf-8")


class Control:
    def __init__(self):
        self.stop = asyncio.Event()
        self.microphone_muted = False
        self.output_muted = False
        self.session = None
        self.cancel_generation = None

    def command(self, value):
        if value.get("command") == "stop":
            if callable(self.cancel_generation):
                self.cancel_generation()
            cancel = getattr(self.session, "cancel", None)
            if callable(cancel):
                cancel("voice_stopped")
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
                for line in _control_lines(sys.stdin):
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            loop.call_soon_threadsafe(self.command, value)
                    except ValueError:
                        continue
                loop.call_soon_threadsafe(self.stop.set)
            except RuntimeError:
                pass                        # event loop has already closed
            except Exception as error:
                try:
                    loop.call_soon_threadsafe(lambda message=str(error): report("error", message=message))
                except (RuntimeError, TypeError):
                    pass
                try:
                    loop.call_soon_threadsafe(self.stop.set)
                except RuntimeError:
                    pass
        threading.Thread(target=read, daemon=True, name="voice-control").start()


class PipeBody(BodySink):
    def write(self, event):
        report("body", event=event)


async def voice(cfg, control):
    from nova_link import NovaLink, new_request_id
    from stt import make_stt, local_asset_status
    from tts import make_tts
    from speech import SpeechPlayer
    from turns import VoiceSession

    # Never fall back to stdin/null and pretend a desktop microphone is active.
    report("state", state="starting", reason="Loading local speech recognition and voice")
    if control.stop.is_set():
        return
    stt = await asyncio.to_thread(make_stt, cfg, allow_fallback=False)
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
            cancellation_tasks, cancellation_ids = set(), set()
            async def cancel_requests(ids):
                for request_id in ids:
                    try:
                        matched = await link.stop(request_id, timeout_s=2)
                        body.emit("diagnostic", level="info", request_id=request_id,
                                  message=("Prior voice request cancellation accepted." if matched else
                                           "Prior voice request was no longer active; no other request was stopped."))
                    except Exception as error:
                        body.emit("diagnostic", level="warn", request_id=request_id,
                                  message=f"Voice request cancellation was not confirmed ({type(error).__name__}); "
                                          "Nova may still be finishing that request. Audio is stopped locally.")
            def schedule_cancellation():
                ids = [rid for rid, pending in session.pending.items()
                       if pending.eligible and rid not in cancellation_ids]
                if not ids:
                    return None
                cancellation_ids.update(ids)
                task = asyncio.create_task(cancel_requests(ids))
                cancellation_tasks.add(task)
                task.add_done_callback(cancellation_tasks.discard)
                return task
            control.cancel_generation = schedule_cancellation
            def recognition_state(state):
                if control.stop.is_set():
                    return
                if state == "transcribing" and not player.active():
                    body.emit("state", state="transcribing")
                elif state == "listening":
                    session._settle()
            stt.on_state = recognition_state
            stt.on_diagnostic = lambda message: report("body", event={"type": "diagnostic", "level": "warning", "message": message})
            stt.gate = lambda: not control.microphone_muted and (cfg.duplex == "full" or not player.busy())
            if cfg.duplex == "full" and cfg.barge_in:
                def barge_in():
                    schedule_cancellation()
                    session.barge_in()
                stt.on_speech_start = barge_in
            async def mic():
                async for text in stt.utterances():
                    if control.stop.is_set():
                        return
                    if control.microphone_muted:
                        continue
                    report("transcript", text=text)
                    cancellation = schedule_cancellation()
                    request_id = new_request_id()
                    session.sent(request_id, text)       # retire old audio immediately, before cancellation I/O
                    if cancellation is not None:
                        await cancellation
                    if control.stop.is_set():
                        return
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
            report("state", state="listening", reason="Voice connected", backends={"input": stt.name, "input_label": local_asset_status(cfg).get("label", stt.name),
                        "output": tts.name, "vad": cfg.vad_backend})
            try:
                done, _ = await asyncio.wait(parts[:3], return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    if not task.cancelled() and task.exception():
                        raise task.exception()
                if not control.stop.is_set():
                    raise RuntimeError("Voice connection or microphone ended; start voice again to reconnect")
            finally:
                schedule_cancellation()             # EOF/orphan shutdown follows the same owned path
                session.cancel("voice_stopped")
                if cancellation_tasks:
                    await asyncio.gather(*list(cancellation_tasks), return_exceptions=True)
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
        control.cancel_generation = None


async def microphone_test(cfg, control):
    """Six seconds of in-memory metering. No transcript, disk audio or model call."""
    if control.stop.is_set():
        report("test", kind="microphone", state="cancelled", message="Microphone test stopped")
        return
    import numpy as np
    import sounddevice as sd
    levels = []
    peak = [0.0]
    def audio(indata, frames, timing, status):
        signal = np.asarray(indata)
        peak[0] = max(peak[0], float(np.max(np.abs(signal))))
        levels.append(float(np.mean(signal ** 2)))
    if control.stop.is_set():
        report("test", kind="microphone", state="cancelled", message="Microphone test stopped")
        return
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
    report("state", state="starting" if mode == "run" else "testing",
           reason="Preparing voice worker and local audio libraries")
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
