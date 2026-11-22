"""Own the Qt application, single-instance handoff, and background worker."""

import os
import signal
import sys
import threading
from pathlib import Path

from heybaby.core.session import DesktopSession


def run_desktop(voice_factory, execute, *, background=False):
    from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from heybaby.desktop.panel import Bridge, Panel

    app = QApplication([sys.argv[0]])
    app.setApplicationName("Hey Baby")
    app.setQuitOnLastWindowClosed(False)
    data = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    data.mkdir(parents=True, exist_ok=True)
    endpoint = str(data / "panel.sock")
    instance = QLockFile(str(data / "instance.lock"))
    instance.setStaleLockTime(0)
    if not instance.tryLock(0):
        socket = QLocalSocket()
        socket.connectToServer(endpoint)
        if socket.waitForConnected(1000):
            return
        raise SystemExit("Hey Baby is already running or starting. Use its menu bar icon.")
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    QLocalServer.removeServer(endpoint)
    if not server.listen(endpoint):
        print(f"Could not enable reopening from Finder: {server.errorString()}", file=sys.stderr)
    bridge = Bridge()
    session = DesktopSession(voice_factory, execute,
                             lambda event, *args: bridge.event.emit(event, args))
    panel = Panel(session, bridge, background=background)
    bridge.activate.connect(panel.activate_from_shortcut)

    def reopen():
        socket = server.nextPendingConnection()
        if socket:
            socket.disconnectFromServer()
            socket.deleteLater()
        panel.reveal()
        panel.activateWindow()

    server.newConnection.connect(reopen)
    app.aboutToQuit.connect(session.closed.set)
    interrupted = False

    def interrupt(*_):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    timer = QTimer()
    timer.timeout.connect(lambda: session.quit() if interrupted else None)
    timer.start(200)
    if not background or not QSystemTrayIcon.isSystemTrayAvailable():
        panel.reveal()
    worker = threading.Thread(target=session.run, daemon=True)
    worker.start()

    hotkeys = None
    try:
        if app.platformName() not in {"offscreen", "minimal"} and (
            sys.platform != "linux" or os.getenv("DISPLAY")
        ):
            from heybaby.integrations.hotkeys import start_global_hotkeys
            hotkeys = start_global_hotkeys(
                bridge.activate.emit, hold_enabled=panel.hold_enabled.is_set,
                on_hold=bridge.hold.emit, on_dictation=bridge.dictate.emit,
                on_insert=bridge.insert_dictation.emit,
                on_status=lambda available: bridge.event.emit("shortcut_status", (available,)))
    except Exception as exc:
        print(f"Global shortcut unavailable: {exc}", file=sys.stderr)

    app.exec()
    session.closed.set()
    if hotkeys:
        hotkeys.stop()
    worker.join(timeout=1)
