#!/usr/bin/env python3
"""
Hey Baby's global keyboard shortcuts.
"""

import sys
import threading
from typing import Callable, Optional

try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

MAC_COMMAND_KEYCODES = {54, 55}


def mac_command_intercept(on_tap, hold_enabled=lambda: False, on_hold=lambda _: None):
    from Quartz import (
        CGEventGetFlags, CGEventGetIntegerValueField, kCGEventFlagsChanged,
        kCGEventFlagMaskAlternate, kCGEventFlagMaskCommand, kCGEventFlagMaskControl,
        kCGEventFlagMaskSecondaryFn, kCGEventFlagMaskShift, kCGEventKeyDown,
        kCGKeyboardEventKeycode, kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput,
    )

    modifiers = (kCGEventFlagMaskAlternate | kCGEventFlagMaskSecondaryFn
                 | kCGEventFlagMaskControl | kCGEventFlagMaskShift)
    standalone_key = None
    command_down = False
    holding = False

    def intercept(event_type, event):
        nonlocal standalone_key, command_down, holding
        if event_type in {kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput}:
            standalone_key, command_down = None, False
            if holding:
                holding = False
                on_hold("cancel")
            return event
        if event_type == kCGEventFlagsChanged:
            flags = CGEventGetFlags(event)
            key = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if key in MAC_COMMAND_KEYCODES:
                if not flags & kCGEventFlagMaskCommand:
                    tapped = standalone_key == key
                    standalone_key = None
                    if holding:
                        holding = False
                        on_hold("finish" if tapped else "cancel")
                    elif tapped and not hold_enabled():
                        on_tap()
                elif not command_down and not flags & modifiers:
                    standalone_key = key
                    if key == 54 and hold_enabled():
                        holding = True
                        on_hold("start")
                else:
                    standalone_key = None
                command_down = bool(flags & kCGEventFlagMaskCommand)
            else:
                standalone_key = None
        elif event_type == kCGEventKeyDown:
            standalone_key = None
        if holding and standalone_key is None:
            holding = False
            on_hold("cancel")
        return event

    return intercept


class GlobalHotkeyService:
    def __init__(self, on_trigger: Callable[[], None], *, hold_enabled, on_hold,
                 on_dictation, on_insert, on_status):
        self.on_trigger = on_trigger
        self.hold_enabled = hold_enabled
        self.on_hold = on_hold
        self.on_dictation = on_dictation
        self.on_insert = on_insert
        self.on_status = on_status
        self.hotkeys_listener: Optional[keyboard.GlobalHotKeys] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self):
        if not HAS_PYNPUT:
            print("[WARN] pynput not installed. Global hotkeys disabled.")
            self.on_status(False)
            return

        def _hotkey_action():
            try:
                self.on_trigger()
            except Exception as e:
                print(f"[WARN] Hotkey callback error: {e}")

        # Map Option+Space and Cmd+Shift+S
        hotkey_map = {
            "<alt>+<space>": _hotkey_action,
            "<cmd>+<shift>+s": _hotkey_action,
            "<alt>+<shift>+d": self.on_dictation,
        }

        try:
            options = {}
            listener_class = keyboard.GlobalHotKeys
            if sys.platform == "darwin":
                hotkey_map["<alt>+<shift>+i"] = self.on_insert
                from Quartz import (CGEventTapCreate, CGEventTapEnable,
                                    kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput,
                                    kCGEventTapOptionListenOnly, kCGHeadInsertEventTap, kCGSessionEventTap)

                class ListenOnlyHotKeys(keyboard.GlobalHotKeys):
                    # Command detection reads events without changing or suppressing them.
                    def _create_event_tap(self):
                        tap = CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap,
                                               kCGEventTapOptionListenOnly, self._EVENTS,
                                               self._receive_event, None)
                        self.event_tap = tap
                        status = ("Command key monitoring active." if tap is not None else
                                  "Keyboard monitoring unavailable. Check Input Monitoring in System Settings.")
                        print(f"[HOTKEY] {status}", file=sys.stderr)
                        self.owner_status(tap is not None)
                        return tap

                    def _receive_event(self, proxy, event_type, event, refcon):
                        if event_type in {kCGEventTapDisabledByTimeout,
                                          kCGEventTapDisabledByUserInput}:
                            CGEventTapEnable(self.event_tap, True)
                            self.reset_shortcut(event_type, event)
                            return event
                        return self._handler(proxy, event_type, event, refcon)

                listener_class = ListenOnlyHotKeys
                options["darwin_intercept"] = mac_command_intercept(
                    _hotkey_action, self.hold_enabled, self.on_hold)
            else:
                hotkey_map["<f8>"] = _hotkey_action
            self.hotkeys_listener = listener_class(hotkey_map, **options)
            if sys.platform == "darwin":
                self.hotkeys_listener.owner_status = self.on_status
                self.hotkeys_listener.reset_shortcut = options["darwin_intercept"]
            self._is_running = True

            def _run():
                try:
                    with self.hotkeys_listener as h:
                        if sys.platform != "darwin":
                            self.on_status(True)
                        h.join()
                except Exception as e:
                    print(f"[NOTE] Global hotkey monitoring paused ({e}).")
                    if sys.platform == "darwin":
                        print("       Check System Settings → Privacy & Security → Input Monitoring.")
                finally:
                    self.on_status(False)

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()
        except Exception as e:
            print(f"[WARN] Failed to register global hotkey: {e}")
            self.on_status(False)

    def stop(self):
        if self.hotkeys_listener and self._is_running:
            try:
                self.hotkeys_listener.stop()
            except Exception:
                pass
            self._is_running = False


_hotkey_instance: Optional[GlobalHotkeyService] = None


def start_global_hotkeys(on_trigger: Callable[[], None], **options) -> GlobalHotkeyService:
    global _hotkey_instance
    if _hotkey_instance is None:
        _hotkey_instance = GlobalHotkeyService(on_trigger, **options)
        _hotkey_instance.start()
    return _hotkey_instance
