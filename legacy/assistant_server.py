#!/usr/bin/env python3
"""
Hey Saran - Asynchronous Backend Server & IPC Controller
Provides:
1. Static HTTP file server for Siri-style Frontend (http://127.0.0.1:8765/)
2. WebSocket Real-Time IPC Server (ws://127.0.0.1:8765/ws)
3. Bidirectional event synchronization between Python voice assistant and web frontend
4. Wake-word activation coordination and audio pause controls
"""

import asyncio
import http.server
import json
import os
import socketserver
import threading
import time
from typing import Set, Optional, Callable, Dict, Any

import websockets
from websockets.asyncio.server import serve, ServerConnection

from heybaby.integrations.sarvam import sarvam
from legacy.notifications import notify_success, notify_error
from legacy.window_manager import get_window_manager

HTTP_PORT = 8765
WS_PORT = 8766


class AssistantServer:
    def __init__(self, ui_dir: str):
        self.ui_dir = os.path.abspath(ui_dir)
        self.clients: Set[ServerConnection] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._httpd: Optional[socketserver.TCPServer] = None
        self.command_handler: Optional[Callable[[str], Any]] = None
        self.manual_listen_trigger: Optional[Callable[[], None]] = None
        self.mode_change_handler: Optional[Callable[[str], None]] = None
        self.wake_pause_event = threading.Event()  # Cleared when active to pause wake-word
        self.wake_pause_event.set()  # Default: allowed to listen
        self.active_mode = "phrase"

    def set_handlers(
        self,
        command_handler: Callable[[str], Any],
        manual_listen_trigger: Optional[Callable[[], None]] = None,
        mode_change_handler: Optional[Callable[[str], None]] = None
    ):
        self.command_handler = command_handler
        self.manual_listen_trigger = manual_listen_trigger
        self.mode_change_handler = mode_change_handler

    # --------------------------------------------------------------------------
    # 1. HTTP Server for Static Assets (ui/index.html, style.css, app.js)
    # --------------------------------------------------------------------------
    def _run_http_server(self):
        ui_dir = self.ui_dir

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=ui_dir, **kwargs)

            def log_message(self, format, *args):
                # Suppress noisy HTTP asset logs
                pass

        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        try:
            with ReusableTCPServer(("127.0.0.1", HTTP_PORT), Handler) as httpd:
                self._httpd = httpd
                print(f"[HTTP] Siri Assistant Frontend served at: http://127.0.0.1:{HTTP_PORT}/")
                httpd.serve_forever()
        except OSError as e:
            print(f"[WARN] HTTP Server on port {HTTP_PORT} encountered: {e}")

    # --------------------------------------------------------------------------
    # 2. WebSocket Real-Time IPC Server
    # --------------------------------------------------------------------------
    async def _ws_handler(self, websocket: ServerConnection):
        self.clients.add(websocket)
        try:
            # Send initial state
            await websocket.send(json.dumps({
                "event": "status_info",
                "sarvam_available": sarvam.is_available(),
                "active_mode": self.active_mode
            }))

            async for message in websocket:
                try:
                    payload = json.loads(message)
                    await self._handle_client_message(websocket, payload)
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)

    async def _handle_client_message(self, websocket: ServerConnection, payload: Dict[str, Any]):
        msg_type = payload.get("type")

        if msg_type == "get_status":
            await websocket.send(json.dumps({
                "event": "status_info",
                "sarvam_available": sarvam.is_available(),
                "active_mode": self.active_mode
            }))

        elif msg_type == "user_text":
            text = payload.get("text", "").strip()
            if text and self.command_handler:
                # Run command in thread to prevent blocking WebSocket event loop
                threading.Thread(target=self._process_user_command, args=(text,), daemon=True).start()

        elif msg_type == "start_listening":
            if self.manual_listen_trigger:
                threading.Thread(target=self.manual_listen_trigger, daemon=True).start()

        elif msg_type == "minimize_window":
            wm = get_window_manager()
            wm.minimize()

        elif msg_type == "set_mode":
            mode = payload.get("mode", "phrase")
            self.active_mode = mode
            if self.mode_change_handler:
                self.mode_change_handler(mode)
            self.broadcast_event({
                "event": "status_info",
                "sarvam_available": sarvam.is_available(),
                "active_mode": mode
            })

        elif msg_type == "test_notification":
            notify_success("Hey Saran popup notification test passed!", subtitle="Test Notification")

        elif msg_type == "test_voice":
            from hey_saran import speak
            threading.Thread(target=speak, args=("Hello Saran. Bulbul voice synthesis is working perfectly.",), daemon=True).start()

    def _process_user_command(self, text: str):
        """Processes command sent from UI input box."""
        if not self.command_handler:
            return

        self.wake_pause_event.clear()
        try:
            self.broadcast_event({"event": "state", "status": "thinking"})
            self.command_handler(text)
        finally:
            self.broadcast_event({"event": "state", "status": "idle"})
            self.wake_pause_event.set()

    # --------------------------------------------------------------------------
    # 3. Public API: Broadcasting Events to Frontend
    # --------------------------------------------------------------------------
    def broadcast_event(self, payload: Dict[str, Any]):
        """Dispatches an event payload to all connected frontend clients."""
        if not self._loop or not self.clients:
            return

        message = json.dumps(payload)

        async def _send_all():
            disconnected = set()
            for client in list(self.clients):
                try:
                    await client.send(message)
                except Exception:
                    disconnected.add(client)
            self.clients.difference_update(disconnected)

        asyncio.run_coroutine_threadsafe(_send_all(), self._loop)

    def trigger_wake_word_activated(self, wake_name: str = "Hey Saran"):
        """
        Called when wake word is detected:
        1. Brings native window to the foreground.
        2. Sends wake_word_triggered to the UI (orb pulses in listening mode).
        """
        # Focus native window automatically
        wm = get_window_manager()
        wm.show_and_focus()

        # Send instant visual activation to frontend
        self.broadcast_event({
            "event": "wake_word_triggered",
            "wake_word": wake_name
        })

    def start_background_servers(self):
        """Starts HTTP and WebSocket servers in background threads."""
        # 1. HTTP server thread
        http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        http_thread.start()

        # 2. WebSocket server thread
        def _run_ws():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _start():
                try:
                    server = await serve(self._ws_handler, "127.0.0.1", WS_PORT)
                    print(f"[WS] WebSocket IPC Server listening at: ws://127.0.0.1:{WS_PORT}")
                    await server.wait_closed()
                except OSError as e:
                    print(f"[WARN] WebSocket server port collision ({e}). Reusing socket if active.")

            self._loop.run_until_complete(_start())
            self._loop.run_forever()

        ws_thread = threading.Thread(target=_run_ws, daemon=True)
        ws_thread.start()
        time.sleep(0.3)  # Brief warmup


# Singleton assistant server
_assistant_server: Optional[AssistantServer] = None


def get_assistant_server(ui_dir: Optional[str] = None) -> AssistantServer:
    global _assistant_server
    if _assistant_server is None:
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
        _assistant_server = AssistantServer(ui_dir or default_dir)
    return _assistant_server
