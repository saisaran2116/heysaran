"""On-device recognition. Audio is neither saved nor sent over a network."""

import json
import time
from pathlib import Path

from heybaby.core.phrases import wake_command


DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "vosk-model-small-en-in-0.4"


class LocalVoice:
    def __init__(self, model_path):
        import sounddevice
        from vosk import KaldiRecognizer, Model, SetLogLevel

        if not (Path(model_path) / "conf" / "model.conf").is_file():
            raise RuntimeError("Speech model missing. Run setup.py to install it.")
        SetLogLevel(-1)
        self.model = Model(str(model_path))
        self.recognizer = KaldiRecognizer
        self.audio = sounddevice

    def listen(self, interrupted, timeout=None, *, continuous=False, released=None, on_open=None):
        if interrupted() or (released and released.is_set()):
            return ""
        try:
            device = self.audio.query_devices(kind="input")
        except self.audio.PortAudioError as exc:
            raise RuntimeError("Microphone unavailable. Connect a mic or check system permissions, then retry.") from exc
        rate = int(device["default_samplerate"])
        decoder = self.recognizer(self.model, rate)
        block = rate // 10
        parts = []
        with self.audio.RawInputStream(samplerate=rate, blocksize=block,
                                       channels=1, dtype="int16") as stream:
            if interrupted():
                return ""
            if on_open:
                on_open()
            deadline = None if timeout is None else time.monotonic() + timeout
            while not interrupted():
                if ((deadline is not None and time.monotonic() >= deadline)
                        or (released and released.is_set())):
                    parts.append(json.loads(decoder.FinalResult()).get("text", ""))
                    return " ".join(filter(None, parts))
                data, _ = stream.read(block)
                if decoder.AcceptWaveform(bytes(data)):
                    text = json.loads(decoder.Result()).get("text", "")
                    if continuous:
                        parts.append(text)
                    elif text and (timeout is not None or wake_command(text) is not None):
                        return text
        return ""
