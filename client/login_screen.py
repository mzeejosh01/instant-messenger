"""
client/login_screen.py - Login screen frame.

Shown on startup. The user enters a username and clicks Connect.
Emits a "login" event to the server; the result is handled in
MessengerApp._on_login_ok / _on_login_error.
"""

import tkinter as tk
from tkinter import ttk


class LoginScreen(tk.Frame):
    """
    A Tkinter Frame that presents a username entry field and a Connect button.

    Attributes:
        app: Reference to the parent MessengerApp instance.
    """

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg="#1e1e2e")
        self.app = app
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct and lay out all widgets."""
        # Centre column
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
        # Allow pressing Enter to connect
        entry.bind("<Return>", lambda _: self._connect())

        self._connect_btn = ttk.Button(card, text="Connect →", command=self._connect)
        self._connect_btn.pack(fill="x", ipady=4)

        self._error_label = tk.Label(
            card, text="", font=("Helvetica", 10),
            bg="#2a2a3e", fg="#f38ba8",
        )
        self._error_label.pack(pady=(10, 0))

    def _connect(self) -> None:
        """Validate input and emit login event."""
        username = self._username_var.get().strip()
        if not username:
            self.show_error("Please enter a username.")
            return

        if not self.app.socket.connected:
            self.show_error("Not connected to server yet. Please wait…")
            return

        self.show_error("")                     
        self._connect_btn.config(state="disabled")
        self.app.socket.emit("login", {"username": username})

    def show_error(self, message: str) -> None:
        """Display an error message and re-enable the connect button."""
        self._error_label.config(text=message)
        self._connect_btn.config(state="normal")
