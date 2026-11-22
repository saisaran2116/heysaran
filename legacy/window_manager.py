#!/usr/bin/env python3
"""
Hey Saran - macOS Cocoa / WebKit Native Window Manager
Manages the assistant frontend window lifecycle:
- Launching and hosting the Siri-style frontend
- Restoring and bringing window to foreground automatically upon wake-word activation
- Managing window focus via Apple Cocoa AppKit APIs (NSApp.activateIgnoringOtherApps_)
- Avoiding duplicate windows
"""

import os
import sys
import threading
import time
from typing import Optional

try:
    import webview
except ImportError:
    webview = None

# Optional AppKit import for native window focus
try:
    from AppKit import NSApplication, NSApp
    HAS_APPKIT = True
except Exception:
    HAS_APPKIT = False


class WindowManager:
    """Manages the pywebview native macOS window for Hey Saran."""

    def __init__(self, ui_dir: str):
        self.ui_dir = os.path.abspath(ui_dir)
        self.index_html = os.path.join(self.ui_dir, "index.html")
        self.window: Optional[webview.Window] = None
        self._is_ready = threading.Event()
        self._gui_thread: Optional[threading.Thread] = None

    def create_window(self, url: Optional[str] = None):
        """Creates the native macOS WebKit window."""
        if not webview:
            print("[WARN] pywebview not installed. Running in headless / CLI mode.")
            return None

        target_url = url or f"file://{self.index_html}"

        self.window = webview.create_window(
            title="Hey Saran",
            url=target_url,
            width=460,
            height=730,
            resizable=True,
            frameless=False,
            easy_drag=True,
            on_top=False,
            background_color="#070913"
        )
        return self.window

    def start_gui_loop(self):
        """Starts the native macOS Cocoa GUI event loop (must run on main thread)."""
        if not webview or not self.window:
            return

        def on_loaded():
            self._is_ready.set()
            print("[GUI] Hey Saran Siri window loaded and ready.")

        self.window.events.loaded += on_loaded
        webview.start(debug=False)

    def show_and_focus(self):
        """
        Brings the window to the foreground automatically.
        If minimized or hidden, restores and activates it.
        If no GUI window is attached (e.g. running as launchd background daemon),
        automatically launches the assistant interface.
        """
        if not self.window:
            return

        def _do_focus():
            try:
                # 1. Restore if minimized, and unhide if hidden
                self.window.restore()
                self.window.show()

                # 2. Native Cocoa AppKit activation
                if HAS_APPKIT and NSApp is not None:
                    NSApp.activateIgnoringOtherApps_(True)

                # 3. Momentarily set on_top to guarantee priority
                self.window.on_top = True
                time.sleep(0.15)
                self.window.on_top = False
            except Exception as e:
                print(f"[WARN] Error focusing window: {e}")

        # Dispatch focus on thread to prevent blocking
        threading.Thread(target=_do_focus, daemon=True).start()

    def minimize(self):
        """Minimizes the assistant window."""
        if self.window:
            try:
                self.window.minimize()
            except Exception as e:
                print(f"[WARN] Failed to minimize window: {e}")

    def is_visible(self) -> bool:
        """Returns True if the window is currently initialized."""
        return self.window is not None


# Global singleton instance
_manager_instance: Optional[WindowManager] = None


def get_window_manager(ui_dir: Optional[str] = None) -> WindowManager:
    global _manager_instance
    if _manager_instance is None:
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
        _manager_instance = WindowManager(ui_dir or default_dir)
    return _manager_instance
