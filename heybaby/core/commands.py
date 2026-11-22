"""Built-in actions. Speech and chat are never interpreted as shell code."""

import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from heybaby.core.session import PAUSE, QUIT, RESUME, STOP
from heybaby.core.phrases import normalize, wake_command

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
APPS = {
    "notes": ("Notes", "notepad.exe", "gedit"),
    "calculator": ("Calculator", "calc.exe", "gnome-calculator"),
    "calendar": ("Calendar", None, "gnome-calendar"),
    "settings": ("System Settings", None, "gnome-control-center"),
    "safari": ("Safari", None, None),
    "chrome": ("Google Chrome", None, "google-chrome"),
    "music": ("Music", None, None),
    "spotify": ("Spotify", None, "spotify"),
    "mail": ("Mail", None, None),
}


def run(argv, session, *, text=None, capture=False):
    if session.cancel.is_set():
        return None
    with subprocess.Popen(argv, stdin=subprocess.PIPE if text is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, text=True, encoding="utf-8") as process:
        try:
            while not session.cancel.is_set():
                try:
                    output, _ = process.communicate(text, timeout=0.15)
                    return (process.returncode, output or "")
                except subprocess.TimeoutExpired:
                    text = None
        finally:
            if process.poll() is None:
                process.kill()


def respond(text, session, speak=True):
    if session.cancel.is_set():
        return
    session.emit("response", text)
    if not speak:
        return
    if IS_MAC:
        argv = ["/usr/bin/say", "-f", "-"]
    elif IS_WINDOWS:
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::InputEncoding = [Text.UTF8Encoding]::new(); "
                "Add-Type -AssemblyName System.Speech; "
                "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([Console]::In.ReadToEnd())"]
    else:
        voice = shutil.which("espeak-ng") or shutil.which("espeak")
        if not voice:
            return
        argv = [voice, "--stdin"]
    session.emit("state", "speaking", "Speaking…")
    run(argv, session, text=text + "\n")


def execute(text, session):
    heard = wake_command(text)
    command = normalize(text) if heard is None else heard
    if command in STOP | PAUSE | RESUME | QUIT:
        session.submit(command)
        return
    if session.cancel.is_set():
        return

    if command in {"help", "what can you do", "show commands"}:
        session.emit("help")
        return
    if command in {"time", "what time is it", "tell me the time", "current time"}:
        respond(f"It’s {datetime.now():%I:%M %p}.", session)
        return
    if command in {"date", "what is the date", "whats the date", "todays date", "what day is it"}:
        respond(f"Today is {datetime.now():%A, %B %d, %Y}.", session)
        return

    search = re.fullmatch(r"(?:search(?: google)? for|google) (.+)", command)
    youtube = re.fullmatch(r"(?:play|search for) (.+) on youtube", command)
    if youtube or search or command in {"open browser", "open youtube"}:
        if youtube:
            url = "https://www.youtube.com/results?search_query=" + quote_plus(youtube[1])
        elif search:
            url = "https://www.google.com/search?q=" + quote_plus(search[1])
        else:
            url = "https://www.youtube.com/" if command == "open youtube" else "https://www.google.com/"
        opened = webbrowser.open(url)
        respond("Opened your browser." if opened else "I couldn’t open your browser.", session)
        return

    target = re.fullmatch(r"(?:open|launch|start) (.+)", command)
    target = target[1] if target else command
    if target in {"finder", "files", "file explorer", "downloads"}:
        path = str(Path.home() / "Downloads" if target == "downloads" else Path.home())
        if IS_WINDOWS:
            os.startfile(path)
            result = (0, "")
        else:
            result = run(["open" if IS_MAC else "xdg-open", path], session)
        if result:
            respond("Opened your files." if result[0] == 0 else "I couldn’t open that folder.", session)
        return
    if target in APPS:
        app = APPS[target][0 if IS_MAC else 1 if IS_WINDOWS else 2]
        if not app or (not IS_MAC and not shutil.which(app)):
            respond(f"I couldn’t find {target} on this laptop.", session)
            return
        if IS_MAC:
            result = run(["open", "-a", app], session)
        elif not session.cancel.is_set():
            subprocess.Popen([app], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result = (0, "")
        else:
            return
        if result:
            respond(f"Opened {target}." if result[0] == 0 else f"I couldn’t open {target}.", session)
        return

    if command in {"take a screenshot", "take screenshot", "screenshot", "capture screen"}:
        if not IS_MAC:
            respond("Screenshot commands are available on macOS.", session)
            return
        path = Path.home() / "Desktop" / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
        result = run(["screencapture", "-x", str(path)], session)
        if result:
            respond("Screenshot saved to your Desktop." if result[0] == 0 and path.exists()
                    else "Screenshot failed. Check Screen Recording permission.", session)
        return
    if command in {"lock screen", "lock the screen", "lock my mac", "lock mac"}:
        argv = (["pmset", "displaysleepnow"] if IS_MAC else
                ["rundll32.exe", "user32.dll,LockWorkStation"] if IS_WINDOWS else ["loginctl", "lock-session"])
        result = run(argv, session)
        if result and result[0] != 0:
            respond("I couldn’t lock your screen.", session)
        return

    volume = {
        "mute": "set volume with output muted",
        "mute audio": "set volume with output muted",
        "unmute": "set volume without output muted",
        "unmute audio": "set volume without output muted",
        "volume up": "set volume output volume ((output volume of (get volume settings)) + 10)",
        "volume down": "set volume output volume ((output volume of (get volume settings)) - 10)",
    }
    level = re.fullmatch(r"(?:set )?volume (?:to )?(\d{1,3})(?: percent)?", command)
    if command in volume or level:
        if not IS_MAC:
            respond("Volume commands are available on macOS.", session)
            return
        script = f"set volume output volume {min(100, int(level[1]))}" if level else volume[command]
        result = run(["osascript", "-e", script], session)
        if result:
            respond("Volume updated." if result[0] == 0 else "I couldn’t change the volume.", session, speak=False)
        return

    media = {"play music": "play", "resume music": "play", "pause music": "pause",
             "stop music": "pause", "next track": "next track", "previous track": "previous track"}
    if command in media:
        if not IS_MAC:
            respond("Music controls are available on macOS.", session)
            return
        result = run(["osascript", "-e", f'tell application "Music" to {media[command]}'], session)
        if result:
            respond("Music updated." if result[0] == 0 else "I couldn’t control Music. Check Automation permission.", session, speak=False)
        return
    if command in {"battery", "check battery", "battery status"} and IS_MAC:
        result = run(["pmset", "-g", "batt"], session, capture=True)
        if result:
            match = re.search(r"\d+%", result[1])
            respond(f"Your battery is at {match[0]}." if match else "I couldn’t read the battery.", session)
        return

    if os.getenv("HEY_BABY_CLOUD_CHAT") == "1":
        from heybaby.integrations.sarvam import sarvam

        reply = sarvam.chat(text)
        if reply:
            respond(reply, session)
            return
    respond("I don’t know that command. Open Commands to see what I can do.", session)
