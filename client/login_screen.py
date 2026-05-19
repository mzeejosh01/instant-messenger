# client/login_screen.py - the login screen.
#
# This is the first screen the user sees.
# They type a username and click Connect.
# The result comes back as login_ok or login_error from the server.

import tkinter as tk
from tkinter import ttk


class LoginScreen(tk.Frame):
    """
    The login screen frame.

    Attributes:
        app: reference to the MessengerApp so we can call socket methods
    """

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg="#1e1e2e")
        self.app = app
        self._build_ui()

    def _build_ui(self) -> None:
        # centre everything on the screen
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        card = tk.Frame(self, bg="#2a2a3e", padx=40, pady=40)
        card.grid(row=0, column=0)

        tk.Label(
            card, text="APC Instant Messenger",
            font=("Helvetica", 20, "bold"),
            bg="#2a2a3e", fg="#cdd6f4",
        ).pack(pady=(0, 6))

        tk.Label(
            card, text="VUB — Advanced Programming Concepts 2025-2026",
            font=("Helvetica", 10),
            bg="#2a2a3e", fg="#6c7086",
        ).pack(pady=(0, 30))

        tk.Label(
            card, text="Choose a username",
            font=("Helvetica", 12),
            bg="#2a2a3e", fg="#cdd6f4",
        ).pack(anchor="w")

        self._username_var = tk.StringVar()
        entry = ttk.Entry(card, textvariable=self._username_var, width=30,
                          font=("Helvetica", 13))
        entry.pack(pady=(4, 16), ipady=6)
        entry.focus()
        # pressing Enter does the same thing as clicking the button
        entry.bind("<Return>", lambda _: self._connect())

        self._connect_btn = ttk.Button(card, text="Connect ->", command=self._connect)
        self._connect_btn.pack(fill="x", ipady=4)

        self._error_label = tk.Label(
            card, text="", font=("Helvetica", 10),
            bg="#2a2a3e", fg="#f38ba8",
        )
        self._error_label.pack(pady=(10, 0))

    def _connect(self) -> None:
        # check the input and send the login event to the server
        username = self._username_var.get().strip()
        if not username:
            self.show_error("Please enter a username.")
            return

        if not self.app.socket.connected:
            self.show_error("Not connected to server yet. Please wait...")
            return

        self.show_error("")
        self._connect_btn.config(state="disabled")
        self.app.socket.emit("login", {"username": username})

    def show_error(self, message: str) -> None:
        # show an error message and re-enable the button
        self._error_label.config(text=message)
        self._connect_btn.config(state="normal")
