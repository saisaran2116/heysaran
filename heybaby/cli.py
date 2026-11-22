#!/usr/bin/env python3
"""Hey Baby desktop assistant entry point."""

import argparse
import os

from heybaby.core.session import DesktopSession
from heybaby.integrations.speech import DEFAULT_MODEL, LocalVoice


def main():
    parser = argparse.ArgumentParser(description="Hey Baby desktop voice assistant")
    parser.add_argument("--model", default=os.getenv("HEY_BABY_MODEL", DEFAULT_MODEL),
                        help="Path to an extracted Vosk English speech model")
    parser.add_argument("--cli", "--no-gui", action="store_true", help="Run without the desktop panel")
    parser.add_argument("--background", action="store_true",
                        help="Wait for the keyboard shortcut or wake phrase without opening the panel")
    parser.add_argument("--check-model", action="store_true",
                        help="Check that the local speech engine and model load without recording")
    args = parser.parse_args()

    if args.check_model:
        voice = LocalVoice(args.model)
        voice.recognizer(voice.model, 16000)
        print("Local speech engine and model are ready.")
        return

    from heybaby.core.commands import execute

    if args.cli:
        last_status = None

        def emit(event, *args):
            nonlocal last_status
            if event == "state":
                if args == last_status:
                    return
                last_status = args
            if event in {"state", "response", "transcript"}:
                print(args[-1], flush=True)

        session = DesktopSession(lambda: LocalVoice(args.model), execute, emit)
        try:
            session.run()
        except KeyboardInterrupt:
            session.quit()
        return

    from heybaby.desktop.runtime import run_desktop

    run_desktop(lambda: LocalVoice(args.model), execute, background=args.background)
