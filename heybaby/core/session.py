"""Owns the microphone and serializes desktop commands in a single worker."""

import queue
import sys
import threading
from dataclasses import dataclass

from heybaby.core.phrases import normalize, wake_command

STOP = {"stop", "cancel", "never mind", "nevermind", "stop talking"}
PAUSE = {"pause listening", "stop listening", "mute microphone", "disable microphone"}
RESUME = {"resume listening", "enable microphone", "unmute microphone"}
QUIT = {"quit", "exit", "quit assistant", "exit assistant", "stop assistant",
        "shutdown assistant", "shut down assistant", "goodbye"}


@dataclass
class VoiceRequest:
    dictation: bool = False
    release: threading.Event | None = None


class DesktopSession:
    def __init__(self, voice_factory, execute, emit):
        self.voice_factory = voice_factory
        self.execute = execute
        self.emit = emit
        self.requests = queue.Queue()
        self.cancel = threading.Event()
        self.closed = threading.Event()
        self.enabled = threading.Event()
        self.enabled.set()
        self.voice_error = None
        self.microphone_ready = False

    def microphone_opened(self):
        if not self.microphone_ready:
            print("[AUDIO] Microphone stream opened.", file=sys.stderr, flush=True)
        self.microphone_ready = True
        self.voice_error = None

    def microphone_failed(self, exc):
        message = str(exc)
        if self.voice_error != message:
            print(f"[AUDIO] {message}", file=sys.stderr, flush=True)
        self.microphone_ready = False
        self.voice_error = message

    def idle_status(self):
        if not self.enabled.is_set():
            return "paused", "Microphone paused"
        if self.voice_error:
            return "error", self.voice_error
        if not self.microphone_ready:
            return "loading", "Opening the microphone…"
        return "ready", "Say “Hey Baby”"

    def submit(self, text):
        command = wake_command(text)
        command = normalize(text) if command is None else command
        if command in STOP:
            self.stop()
        elif command in PAUSE:
            self.set_microphone(False)
        elif command in RESUME:
            self.set_microphone(True)
        elif command in QUIT:
            self.quit()
        elif command:
            self.requests.put(command)

    def listen_now(self, *, dictation=False, release=None):
        if self.enabled.is_set() and not self.closed.is_set() and self.requests.empty():
            self.requests.put(VoiceRequest(dictation, release) if dictation or release else None)
            return True
        return False

    def stop(self):
        self.cancel.set()
        while True:
            try:
                self.requests.get_nowait()
            except queue.Empty:
                break
        self.emit("state", *self.idle_status())

    def set_microphone(self, enabled):
        if enabled:
            self.enabled.set()
            if self.voice_error:
                self.requests.put("")  # Retry opening the microphone.
        else:
            self.enabled.clear()
            self.stop()
        self.emit("state", *self.idle_status())

    def quit(self):
        self.closed.set()
        self.stop()
        self.emit("quit")

    def run(self):
        voice = None
        last_idle = None
        while not self.closed.is_set():
            self.cancel.clear()
            try:
                command = self.requests.get(timeout=0.1) if (
                    not self.enabled.is_set() or self.voice_error
                ) else self.requests.get_nowait()
            except queue.Empty:
                idle = self.idle_status()
                if idle != last_idle:
                    self.emit("state", *idle)
                    last_idle = idle
                if not self.enabled.is_set() or self.closed.is_set():
                    continue
                try:
                    if voice is None:
                        self.emit("state", "loading", "Starting local speech recognition…")
                        voice = self.voice_factory()
                    def ready():
                        nonlocal last_idle
                        self.microphone_opened()
                        status = self.idle_status()
                        if status != last_idle:
                            self.emit("state", *status)
                            last_idle = status

                    heard = voice.listen(lambda: self.cancel.is_set() or not self.enabled.is_set() or
                                         self.closed.is_set() or not self.requests.empty(),
                                         on_open=ready)
                except Exception as exc:
                    self.microphone_failed(exc)
                    self.emit("state", *self.idle_status())
                    self.closed.wait(1)
                    continue
                if self.cancel.is_set() or not self.enabled.is_set() or not self.requests.empty():
                    continue
                command = wake_command(heard)
                if command is None:
                    continue
                self.emit("show")
                if not command:
                    command = None
            last_idle = None
            if command == "":
                if self.enabled.is_set():
                    self.voice_error = None
                continue
            if self.cancel.is_set() or self.closed.is_set():
                continue
            if command is None or isinstance(command, VoiceRequest):
                if not self.enabled.is_set():
                    continue
                request = command or VoiceRequest()
                try:
                    if voice is None:
                        voice = self.voice_factory()
                    self.emit("show")
                    message = ("Speak, then choose Finish dictation." if request.dictation else
                               "Release Right ⌘ to finish." if request.release else
                               "Listening for a command…")
                    def opened():
                        self.microphone_opened()
                        self.emit("state", "listening", message)

                    interrupted = lambda: (self.cancel.is_set() or not self.enabled.is_set()
                                           or self.closed.is_set())
                    if request.release or request.dictation:
                        command = voice.listen(interrupted, timeout=45, continuous=True,
                                               released=request.release, on_open=opened)
                    else:
                        command = voice.listen(interrupted, timeout=7, on_open=opened)
                except Exception as exc:
                    self.microphone_failed(exc)
                    continue
                if request.dictation:
                    if not interrupted():
                        self.emit("dictation", command)
                    continue
                if request.release and not request.release.is_set():
                    command = ""
                if not command and not self.cancel.is_set() and not self.closed.is_set():
                    self.emit("response", "I didn’t hear a command. Press Start listening to try again.")
            if command and not self.cancel.is_set() and not self.closed.is_set():
                self.emit("transcript", command)
                self.emit("state", "working", "Working…")
                try:
                    self.execute(command, self)
                except Exception as exc:
                    if not self.cancel.is_set():
                        self.emit("response", f"Couldn’t complete the command: {exc}")
