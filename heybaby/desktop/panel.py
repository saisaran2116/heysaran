"""Hey Baby's floating command panel and menu bar controls."""

import sys
import threading

from PySide6.QtCore import QObject, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
                               QDialog, QComboBox, QPlainTextEdit)


class Bridge(QObject):
    event = Signal(str, tuple)
    activate = Signal()
    hold = Signal(str)
    dictate = Signal()
    insert_dictation = Signal()


STYLE = """
QLabel { color: #242621; font-size: 13px; }
QLabel#title { font-size: 14px; font-weight: 700; }
QLabel#status { font-size: 24px; font-weight: 650; }
QLabel#muted { color: #595b54; }
QLabel#answer { font-size: 14px; }
QFrame#line { background: #ddd9d0; }
QFrame#reply { background: #efede6; border-radius: 10px; }
QPushButton, QLineEdit, QPlainTextEdit {
    color: #242621; font-size: 13px; background: transparent;
    border: 1px solid transparent; border-radius: 7px; padding: 6px 9px;
}
QPushButton:hover { background: #ebe8df; }
QPushButton:focus, QLineEdit:focus { border-color: #315e4e; }
QPlainTextEdit { background: white; border-color: #d6d2c8; }
QPlainTextEdit:focus { border-color: #315e4e; }
QPushButton:disabled { color: #797b73; }
QPushButton#more::menu-indicator { width: 0px; }
QPushButton#primary { background: #214c3e; color: white; font-weight: 650; padding: 9px 14px; }
QPushButton#primary:hover { background: #173e31; }
QPushButton#primary:focus { border-color: #101b16; }
QPushButton#primary:disabled { background: #dedfd8; color: #555950; }
QPushButton#example { text-align: left; background: #efede6; }
QPushButton#example:hover { background: #e6e3d8; }
QFrame#composer { background: white; border: 1px solid #d6d2c8; border-radius: 9px; }
QMenu { background: #f9f8f4; color: #242621; border: 1px solid #c7c4bc; padding: 5px; }
QMenu::item { padding: 6px 16px; }
QMenu::item:selected { background: #e4ebe4; }
"""


def voice_mark(size, color, background=None):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 48, size / 48)
    if background:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(0, 0, 48, 48, 13, 13)
    pen = QPen(QColor(color), 2.5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    for x, height in zip((12, 18, 24, 30, 36), (7, 15, 23, 15, 7)):
        painter.drawLine(x, 24 - height // 2, x, 24 + height // 2)
    painter.end()
    return pixmap


class Panel(QWidget):
    def __init__(self, session, bridge, background=False):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.session = session
        self.active = False
        self.shortcut_ready = None
        self.hold_enabled = threading.Event()
        self.release = None
        self.dictation_target = None
        self.dictation_release = None
        self.settings = QSettings("Hey Baby", "Hey Baby")
        if self.settings.value("holdRightCommand", False, type=bool):
            self.hold_enabled.set()
        self.setObjectName("panel")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Hey Baby")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(368)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 13)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(self.label("Hey Baby", "title"), 1)
        self.commands = QPushButton("Commands", checkable=True)
        header.addWidget(self.commands)
        hide_panel = QPushButton("Hide")
        hide_panel.setToolTip("Close the panel and keep Hey Baby running")
        hide_panel.clicked.connect(self.dismiss)
        header.addWidget(hide_panel)
        more = QPushButton("⋯", objectName="more")
        more.setAccessibleName("More options")
        more.setToolTip("More options")
        more.setFixedWidth(33)
        header.addWidget(more)
        layout.addLayout(header)
        line = QFrame(objectName="line")
        line.setFixedHeight(1)
        layout.addWidget(line)

        hero = QHBoxLayout()
        hero.setSpacing(12)
        self.mark = QLabel()
        self.mark.setFixedSize(48, 48)
        hero.addWidget(self.mark, 0, Qt.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.status = self.label("", "status")
        self.detail = self.label("", "muted")
        copy.addWidget(self.status)
        copy.addWidget(self.detail)
        hero.addLayout(copy, 1)
        layout.addSpacing(6)
        layout.addLayout(hero)

        self.listen = QPushButton("Start listening", objectName="primary")
        self.listen.clicked.connect(self.voice_action)
        layout.addWidget(self.listen)

        self.reply = QFrame(objectName="reply")
        reply_layout = QVBoxLayout(self.reply)
        reply_layout.setContentsMargins(12, 9, 12, 9)
        reply_layout.setSpacing(4)
        self.transcript = self.label("", "muted")
        self.answer = self.label("", "answer")
        for label in (self.transcript, self.answer):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.hide()
            reply_layout.addWidget(label)
        self.reply.hide()
        layout.addWidget(self.reply)

        composer = QFrame(objectName="composer")
        row = QHBoxLayout(composer)
        row.setContentsMargins(3, 2, 4, 2)
        self.input = QLineEdit(placeholderText="Type a command")
        self.input.setAccessibleName("Type a command")
        self.input.setMaxLength(500)
        self.input.returnPressed.connect(self.submit)
        send = QPushButton("Send")
        send.clicked.connect(self.submit)
        row.addWidget(self.input, 1)
        row.addWidget(send)
        layout.addWidget(composer)

        self.dictation = QPlainTextEdit(placeholderText="Dictation preview")
        self.dictation.setAccessibleName("Dictation preview")
        self.dictation.setMaximumHeight(105)
        self.dictation.hide()
        layout.addWidget(self.dictation)
        self.finish_dictation = QPushButton("Finish dictation")
        self.finish_dictation.clicked.connect(self.finish_dictation_recording)
        self.finish_dictation.hide()
        layout.addWidget(self.finish_dictation)
        self.dictation_tools = QWidget()
        dictation_row = QHBoxLayout(self.dictation_tools)
        dictation_row.setContentsMargins(0, 0, 0, 0)
        self.dictation_hint = self.label("", "muted")
        dictation_row.addWidget(self.dictation_hint, 1)
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy_dictation)
        dictation_row.addWidget(copy)
        self.dictation_tools.hide()
        layout.addWidget(self.dictation_tools)

        self.examples = QWidget()
        examples_layout = QVBoxLayout(self.examples)
        examples_layout.setContentsMargins(0, 0, 0, 0)
        examples_layout.setSpacing(4)
        for label, command in (("Open Calculator", "open calculator"),
                               ("What time is it?", "what time is it"),
                               ("Open Downloads", "open downloads")):
            example = QPushButton(label, objectName="example")
            example.clicked.connect(lambda _checked=False, text=command: self.choose_command(text))
            examples_layout.addWidget(example)
        self.examples.hide()
        self.commands.toggled.connect(self.show_examples)
        layout.addWidget(self.examples)

        footer = QHBoxLayout()
        self.mic_status = self.label("", "muted")
        footer.addWidget(self.mic_status, 1)
        self.microphone = QPushButton("Pause mic")
        self.microphone.clicked.connect(self.toggle_microphone)
        footer.addWidget(self.microphone)
        layout.addLayout(footer)

        self.tray = QSystemTrayIcon(self)
        icon = QIcon(voice_mark(22, "#ffffff", "#214c3e"))
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)
        self.tray.setToolTip("Hey Baby")
        self.menu = QMenu(self)
        self.menu.addAction("Show Hey Baby", self.reveal)
        self.tray_voice = self.menu.addAction("Start listening", self.voice_action)
        self.tray_dictate = self.menu.addAction("Start dictation", self.start_dictation)
        self.menu.addAction("Settings…", self.show_settings)
        self.tray_microphone = self.menu.addAction("Pause microphone", self.toggle_microphone)
        self.menu.addSeparator()
        hide = self.menu.addAction("Hide panel", self.dismiss)
        if not background:
            self.menu.addAction("Quit Hey Baby", session.quit)
        more.setMenu(self.menu)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray)
        hide.setEnabled(QSystemTrayIcon.isSystemTrayAvailable())
        hide_panel.setVisible(hide.isEnabled())
        if hide.isEnabled():
            self.tray.show()
        self.escape = QShortcut(QKeySequence("Escape"), self)
        self.escape.activated.connect(self.escape_pressed)
        self.setTabOrder(self.listen, self.input)
        bridge.event.connect(self.on_event)
        bridge.hold.connect(self.handle_hold)
        bridge.dictate.connect(self.start_dictation)
        bridge.insert_dictation.connect(self.insert_dictation)
        self.on_event("state", ("loading", "Starting local speech recognition…"))

    @staticmethod
    def label(text, name=""):
        label = QLabel(text, objectName=name)
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        return label

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#c7c4bc"))
        painter.setBrush(QColor("#f9f8f4"))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 18, 18)

    def toggle_microphone(self):
        self.session.set_microphone(not self.session.enabled.is_set())

    def voice_action(self):
        if self.active:
            self.release = None
            self.session.stop()
        else:
            self.start_listening()

    @Slot()
    def start_listening(self):
        if not self.active and self.listen.isEnabled() and self.session.listen_now():
            self.on_event("state", ("starting", "Opening the microphone…"))
            self.reveal()

    @Slot()
    def activate_from_shortcut(self):
        print("[HOTKEY] Activation received.", file=sys.stderr, flush=True)
        self.reveal()
        self.start_listening()

    @Slot(str)
    def handle_hold(self, event):
        if event == "start":
            if self.active:
                return
            release = threading.Event()
            if self.session.listen_now(release=release):
                self.release = release
                self.on_event("state", ("starting", "Hold Right ⌘ while you speak."))
                self.reveal()
        elif self.release:
            if event == "finish":
                self.release.set()
            else:
                self.session.stop()
            self.release = None

    @Slot()
    def start_dictation(self):
        release = threading.Event()
        if self.active or not self.session.listen_now(dictation=True, release=release):
            return
        self.dictation_release = release
        self.dictation_target = None
        if sys.platform == "darwin":
            from heybaby.integrations.dictation_target import focused_selection
            try:
                self.dictation_target = focused_selection()
            except RuntimeError:
                pass
        self.dictation.hide()
        self.dictation_tools.hide()
        self.on_event("state", ("starting", "Opening the microphone for dictation…"))
        self.reveal()

    def finish_dictation_recording(self):
        if self.dictation_release:
            self.dictation_release.set()
            self.finish_dictation.hide()

    def copy_dictation(self):
        QApplication.clipboard().setText(self.dictation.toPlainText())
        self.dictation_hint.setText("Copied")

    @Slot()
    def insert_dictation(self):
        if self.dictation_target is None or self.active:
            return
        text = self.dictation.toPlainText().strip()
        if not text:
            return
        from heybaby.integrations.dictation_target import insert
        target, self.dictation_target = self.dictation_target, None
        try:
            insert(target, text)
            self.dictation_hint.setText("Inserted")
        except RuntimeError as exc:
            self.dictation_hint.setText(str(exc))
            self.reveal()

    def show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Hey Baby Settings")
        dialog.setStyleSheet("QDialog { background: #f9f8f4; } QComboBox { color: #242621; background: white; }")
        layout = QVBoxLayout(dialog)
        if sys.platform == "darwin":
            layout.addWidget(self.label("Command key"))
            mode = QComboBox()
            mode.addItems(["Tap either Command key", "Hold Right Command to talk"])
            mode.setCurrentIndex(int(self.hold_enabled.is_set()))
            layout.addWidget(mode)

            def save_mode(index):
                if index:
                    self.hold_enabled.set()
                else:
                    self.hold_enabled.clear()
                self.settings.setValue("holdRightCommand", bool(index))
                if self.status.text() == "Ready":
                    self.on_event("state", self.session.idle_status())

            mode.currentIndexChanged.connect(save_mode)
        mic = ("Paused" if not self.session.enabled.is_set() else
               self.session.voice_error or ("Available" if self.session.microphone_ready else "Checking"))
        layout.addWidget(self.label(f"Microphone: {mic}"))
        status = ("Checking" if self.shortcut_ready is None else
                  "Available" if self.shortcut_ready else "Unavailable")
        layout.addWidget(self.label(f"Global shortcuts: {status}"))
        if self.shortcut_ready is False and sys.platform == "darwin":
            layout.addWidget(self.label("Allow Hey Baby in System Settings → Privacy & Security → Input Monitoring."))
        dialog.setMinimumWidth(320)
        dialog.exec()

    def choose_command(self, text):
        self.input.setText(text)
        self.commands.setChecked(False)
        self.activateWindow()
        self.input.setFocus()

    def submit(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.session.submit(text)

    def escape_pressed(self):
        if self.active:
            self.release = None
            self.session.stop()
        elif self.commands.isChecked():
            self.commands.setChecked(False)
        else:
            self.dismiss()

    def dismiss(self):
        if self.tray.isVisible():
            if self.active:
                self.release = None
                self.session.stop()
            self.hide()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.dismiss()
        else:
            self.session.quit()

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.reveal()

    def position_panel(self, screen):
        if screen:
            area = screen.availableGeometry()
            self.move(max(area.left(), area.right() - self.width() - 20),
                      max(area.top(), area.bottom() - self.height() - 20))

    def fit_panel(self):
        self.adjustSize()
        if self.isVisible():
            self.position_panel(self.screen())

    def reveal(self):
        self.adjustSize()
        self.position_panel(QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen())
        self.show()
        self.raise_()

    def show_examples(self, visible):
        self.examples.setVisible(visible)
        self.fit_panel()

    @Slot(str, tuple)
    def on_event(self, event, args):
        if event == "show":
            self.reveal()
        elif event == "state":
            state, message = args
            self.active = state in {"starting", "listening", "working", "speaking"}
            self.finish_dictation.setVisible(self.dictation_release is not None
                                             and state == "listening"
                                             and message == "Speak, then choose Finish dictation."
                                             and not self.dictation_release.is_set())
            enabled = self.session.enabled.is_set()
            title = {"ready": "Ready", "loading": "Starting…", "starting": "Getting ready…",
                     "listening": "Listening", "working": "Working…", "speaking": "Speaking",
                     "paused": "Microphone paused", "error": "Microphone unavailable"}[state]
            shortcut = "tap ⌘" if sys.platform == "darwin" else "press F8"
            if self.hold_enabled.is_set():
                shortcut = "hold Right ⌘"
            detail = {"ready": f"Say “Hey Baby” or {shortcut}.",
                      "listening": message,
                      "paused": "You can still type a command."}.get(state, message)
            if title != self.status.text() or detail != self.detail.text():
                self.status.setText(title)
                self.detail.setText(detail)
                self.detail.setVisible(title != detail)
                self.mark.setPixmap(voice_mark(48, "#ffffff" if self.active else "#315e4e",
                                               "#214c3e" if self.active else "#e6ece4"))
                if state in {"starting", "listening"}:
                    self.transcript.hide()
                    self.answer.hide()
                    self.reply.hide()
                self.fit_panel()
            action = "Stop" if self.active else "Start listening"
            available = self.active or (enabled and state != "loading")
            self.listen.setText(action)
            self.listen.setEnabled(available)
            self.tray_voice.setText(action)
            self.tray_voice.setEnabled(available)
            self.tray_dictate.setEnabled(enabled and not self.active and state != "loading")
            self.mic_status.setText("Mic paused" if not enabled else
                                    "Checking microphone…" if state == "loading" else
                                    "Mic unavailable" if state == "error" else "Voice processed on device")
            self.microphone.setText("Pause mic" if enabled else "Resume mic")
            self.tray_microphone.setText("Pause microphone" if enabled else "Resume microphone")
        elif event == "shortcut_status":
            self.shortcut_ready = args[0]
        elif event == "dictation":
            self.dictation_release = None
            text = args[0]
            self.dictation.setPlainText(text)
            self.dictation.setVisible(bool(text))
            self.dictation_tools.setVisible(bool(text))
            if text:
                hint = ("Refocus the original editor and press ⌥⇧I to insert."
                        if self.dictation_target and self.shortcut_ready else "Review and copy")
                self.dictation_hint.setText(hint)
                self.fit_panel()
            else:
                self.on_event("response", ("No dictation heard.",))
        elif event == "transcript":
            self.transcript.setText("You: " + args[0][:180])
            self.transcript.show()
            self.answer.hide()
            self.reply.show()
            self.fit_panel()
        elif event == "response":
            self.answer.setText(args[0][:360])
            self.answer.show()
            self.reply.show()
            self.fit_panel()
        elif event == "help":
            self.reveal()
            self.commands.setChecked(True)
        elif event == "quit":
            QApplication.quit()
