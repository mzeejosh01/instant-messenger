# client/app.py - the main application class.
#
# This creates the Tk window, connects to the server,
# and switches between the login screen and the chat screen.
#
# SocketIO callbacks run on a background thread, so any GUI update
# must go through root.after() to run on the main thread.

import tkinter as tk
import socketio as sio

from client.login_screen import LoginScreen
from client.chat_screen import ChatScreen


class MessengerApp:
    """
    The root application class.

    Attributes:
        root     (tk.Tk):      the main Tkinter window
        socket   (sio.Client): the SocketIO client connection
        username (str):        the username set after a successful login
        current_frame:         whichever screen is currently showing
    """

    SERVER_URL = "http://127.0.0.1:5050"

    def __init__(self) -> None:
        # create the main window
        self.root = tk.Tk()
        self.root.title("APC Instant Messenger")
        self.root.geometry("900x600")
        self.root.resizable(True, True)

        self.username: str = ""
        self.current_frame = None

        # set up the SocketIO client
        self.socket = sio.Client(reconnection=True)
        self._register_socket_events()

        # try connecting to the server a few times in case it is not ready yet
        self._connect_with_retry()

        # show the login screen first
        self._show_login()

    def _connect_with_retry(self, attempts: int = 10, delay: float = 0.5) -> None:
        # try connecting to the server in a background thread
        # we retry a few times because the server thread might need a moment to start
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

    # screen switching

    def _show_login(self) -> None:
        # replace the current screen with the login screen
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = LoginScreen(self.root, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_chat(self, username: str, public_rooms: list[dict]) -> None:
        # replace the login screen with the chat screen after a successful login
        self.username = username
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = ChatScreen(self.root, self, public_rooms)
        self.current_frame.pack(fill="both", expand=True)

    # SocketIO event registration

    def _register_socket_events(self) -> None:
        # connect each server event to a handler
        # all GUI updates go through root.after() to stay on the main thread

        @self.socket.on("login_ok")
        def _login_ok(data):
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

        @self.socket.on("invite_sent")
        def _invite_sent(data):
            self.root.after(0, lambda: self._dispatch("invite_sent", data))

        @self.socket.on("user_list_update")
        def _user_list_update(data):
            self.root.after(0, lambda: self._dispatch("user_list_update", data))

        @self.socket.on("public_room_created")
        def _public_room_created(data):
            self.root.after(0, lambda: self._dispatch("public_room_created", data))

        @self.socket.on("error")
        def _error(data):
            self.root.after(0, lambda: self._dispatch("error", data))

    # internal helpers

    def _on_login_ok(self, data: dict) -> None:
        self.show_chat(data["username"], data["public_rooms"])

    def _on_login_error(self, data: dict) -> None:
        # pass the error message to the login screen to display
        if isinstance(self.current_frame, LoginScreen):
            self.current_frame.show_error(data["message"])

    def _dispatch(self, event: str, data: dict) -> None:
        # forward a server event to the chat screen if it is active
        if isinstance(self.current_frame, ChatScreen):
            self.current_frame.handle_event(event, data)

    def run(self) -> None:
        # start the Tkinter main loop
        self.root.mainloop()
        # disconnect the socket when the window is closed
        if self.socket.connected:
            self.socket.disconnect()


def launch_client() -> None:
    # entry point called from main.py
    app = MessengerApp()
    app.run()
