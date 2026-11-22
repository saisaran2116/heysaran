import sys
import threading
import unittest
from unittest.mock import Mock, patch

from heybaby.core.commands import execute, run
from heybaby.core.session import DesktopSession
from heybaby.core.phrases import wake_command


class AssistantTests(unittest.TestCase):
    def test_dictation_preserves_text_without_executing_it(self):
        voice = Mock()
        voice.listen.return_value = "open calculator and then stop"
        execute = Mock()
        events = []

        def emit(event, *args):
            events.append((event, *args))
            if event == "dictation":
                session.quit()

        session = DesktopSession(lambda: voice, execute, emit)
        release = threading.Event()
        self.assertTrue(session.listen_now(dictation=True, release=release))
        session.run()
        self.assertIn(("dictation", "open calculator and then stop"), events)
        self.assertIs(voice.listen.call_args.kwargs["released"], release)
        execute.assert_not_called()

    def test_cancelled_voice_cannot_execute_returned_text(self):
        voice = Mock()
        execute = Mock()

        def cancelled_capture(interrupted, **options):
            session.quit()
            self.assertTrue(interrupted())
            return "open calculator"

        voice.listen.side_effect = cancelled_capture
        session = DesktopSession(lambda: voice, execute, Mock())
        session.listen_now()
        session.run()
        execute.assert_not_called()

    def test_wake_phrase_requires_complete_leading_words(self):
        self.assertEqual(wake_command("Hey, Baby!"), "")
        self.assertEqual(wake_command("Hey Baby, open Notes"), "open notes")
        self.assertEqual(wake_command("Hey Babay, open Notes"), "open notes")
        for utterance in ("Hey Siri", "Hey Saran", "say hey baby", "hey babysitter"):
            self.assertIsNone(wake_command(utterance))

    def test_stop_pause_resume_and_quit_are_distinct(self):
        session = DesktopSession(Mock(), execute, Mock())
        session.submit("why do people stop listening")
        self.assertEqual(session.requests.get_nowait(), "why do people stop listening")
        session.submit("stop music")
        self.assertEqual(session.requests.get_nowait(), "stop music")
        execute("stop", session)
        self.assertTrue(session.cancel.is_set())
        self.assertTrue(session.enabled.is_set())
        self.assertFalse(session.closed.is_set())
        execute("stop listening", session)
        self.assertFalse(session.enabled.is_set())
        session.listen_now()
        self.assertTrue(session.requests.empty())
        session.submit("resume listening")
        self.assertTrue(session.enabled.is_set())
        execute("quit assistant", session)
        self.assertTrue(session.closed.is_set())
        session.emit.assert_called_with("quit")

    def test_voice_session_wakes_and_accepts_followup(self):
        voice = Mock()
        def listen(interrupted, timeout=None, *, on_open):
            on_open()
            return "hey baby" if timeout is None else "what time is it"

        voice.listen.side_effect = listen
        emit = Mock()

        def execute_and_quit(text, session):
            self.assertEqual(text, "what time is it")
            session.quit()

        session = DesktopSession(lambda: voice, execute_and_quit, emit)
        session.run()
        self.assertEqual(voice.listen.call_args.kwargs["timeout"], 7)
        emit.assert_any_call("state", "listening", "Listening for a command…")
        emit.assert_any_call("transcript", "what time is it")

    def test_stop_interrupts_running_playback_process(self):
        session = DesktopSession(Mock(), Mock(), Mock())
        timer = threading.Timer(0.25, session.stop)
        timer.start()
        try:
            self.assertIsNone(run([sys.executable, "-c", "import time; time.sleep(10)"], session))
        finally:
            timer.cancel()

    def test_manual_start_interrupts_standby_and_skips_wake_phrase(self):
        voice = Mock()
        emit = Mock()
        commands = []

        def listen(interrupted, timeout=None, *, on_open):
            on_open()
            if timeout is None:
                self.assertTrue(session.listen_now())
                self.assertTrue(interrupted())
                return ""
            self.assertEqual(timeout, 7)
            return "open calculator"

        def execute_and_quit(command, session):
            commands.append(command)
            session.quit()

        voice.listen.side_effect = listen
        session = DesktopSession(lambda: voice, execute_and_quit, emit)
        session.run()
        self.assertEqual(commands, ["open calculator"])
        emit.assert_any_call("state", "listening", "Listening for a command…")

    def test_system_commands_are_exact_and_mute_does_not_match_unmute(self):
        session = DesktopSession(Mock(), execute, Mock())
        with patch("heybaby.core.commands.IS_MAC", True), patch("heybaby.core.commands.run",
                                                           return_value=(0, "")) as action:
            execute("unmute", session)
            action.assert_called_once_with(["osascript", "-e", "set volume without output muted"], session)
        with patch("heybaby.core.commands.respond") as respond:
            execute("how do i take a screenshot", session)
            self.assertIn("don’t know", respond.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
