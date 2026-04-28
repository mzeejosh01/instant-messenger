"""
client/app.py - Tkinter root window and SocketIO client connection.

This is the top-level client class. It:
  1. Creates the Tk root window.
  2. Opens a socketio-client connection to the server.
  3. Switches between the LoginScreen and ChatScreen frames.

All SocketIO callbacks run on a background thread, so any GUI update
must be scheduled via root.after() to stay on the main thread.
"""

import tkinter as tk
import socketio as sio

from client.login_screen import LoginScreen
from client.chat_screen import ChatScreen


class MessengerApp:
    """
    Root application class.

    Attributes:
        root     (tk.Tk):       The Tk root window.
        socket   (sio.Client):  python-socketio client.
        username (str):         Set after a successful login.
        current_frame           The frame currently visible.
    """

    SERVER_URL = "http://127.0.0.1:5050"

    def __init__(self) -> None:
        # ── Tk root ──────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.title("APC Instant Messenger")
        self.root.geometry("900x600")
        self.root.resizable(True, True)

        self.username: str = ""
        self.current_frame = None

        # ── SocketIO client ──────────────────────────────────────────
        self.socket = sio.Client(reconnection=True)
        self._register_socket_events()

        # Retry connecting — the server thread may need a moment to start.
        self._connect_with_retry()

        # ── Show login screen ────────────────────────────────────────
        self._show_login()

    def _connect_with_retry(self, attempts: int = 10, delay: float = 0.5) -> None:
        """
        Try to connect to the server in a background thread, retrying every
        *delay* seconds. The server thread may need a moment to be ready.
        """
        import time
        import threading

        def _try():
            for i in range(attempts):
                try:
                    self.socket.connect(self.SERVER_URL)
                    print("[client] Connected to server.")
                    return
                except Exception:
                    time.sleep(delay)
            print("[client] ERROR: Could not connect to server after retries.")

        threading.Thread(target=_try, daemon=True).start()

    # ------------------------------------------------------------------
    # Screen switching
    # ------------------------------------------------------------------

    def _show_login(self) -> None:
        """Replace current frame with the LoginScreen."""
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = LoginScreen(self.root, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_chat(self, username: str, public_rooms: list[dict]) -> None:
        """Replace LoginScreen with the ChatScreen after successful login."""
        self.username = username
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = ChatScreen(self.root, self, public_rooms)
        self.current_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # SocketIO event registration
    # ------------------------------------------------------------------

    def _register_socket_events(self) -> None:
        """Bind server events to handler methods."""

        @self.socket.on("login_ok")
        def _login_ok(data):
            # Schedule GUI work on the main thread
            self.root.after(0, lambda: self._on_login_ok(data))

        @self.socket.on("login_error")
        def _login_error(data):
            self.root.after(0, lambda: self._on_login_error(data))

        @self.socket.on("room_joined")
        def _room_joined(data):
            self.root.after(0, lambda: self._dispatch("room_joined", data))

        @self.socket.on("room_created")
        def _room_created(data):
            self.root.after(0, lambda: self._dispatch("room_created", data))

        @self.socket.on("new_message")
        def _new_message(data):
            self.root.after(0, lambda: self._dispatch("new_message", data))

        @self.socket.on("user_joined")
        def _user_joined(data):
            self.root.after(0, lambda: self._dispatch("user_joined", data))

        @self.socket.on("user_left")
        def _user_left(data):
            self.root.after(0, lambda: self._dispatch("user_left", data))

        @self.socket.on("invited_to_room")
        def _invited(data):
            self.root.after(0, lambda: self._dispatch("invited_to_room", data))

        @self.socket.on("error")
        def _error(data):
            self.root.after(0, lambda: self._dispatch("error", data))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_login_ok(self, data: dict) -> None:
        self.show_chat(data["username"], data["public_rooms"])

    def _on_login_error(self, data: dict) -> None:
        """Forward the error message to the login screen."""
        if isinstance(self.current_frame, LoginScreen):
            self.current_frame.show_error(data["message"])

    def _dispatch(self, event: str, data: dict) -> None:
        """Forward a server event to the ChatScreen (if active)."""
        if isinstance(self.current_frame, ChatScreen):
            self.current_frame.handle_event(event, data)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tk main loop (blocks until window is closed)."""
        self.root.mainloop()
        # Clean up the socket when the window closes
        if self.socket.connected:
            self.socket.disconnect()


def launch_client() -> None:
    """Module-level entry point called by Main.py."""
    app = MessengerApp()
    app.run()
