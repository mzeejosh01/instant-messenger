"""
client/chat_screen.py - Main chat interface frame.

Layout:
  ┌──────────────┬────────────────────────────┬──────────────┐
  │  Room list   │      Message display        │ Member list  │
  │  (left)      │      (centre)               │ (right)      │
  │              ├────────────────────────────┤              │
  │              │  Message input + Send btn  │              │
  └──────────────┴────────────────────────────┴──────────────┘

All server events are routed here via MessengerApp._dispatch → handle_event().
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import base64
from io import BytesIO


class ChatScreen(tk.Frame):
    """
    Main chat frame shown after a successful login.

    Attributes:
        app          : Reference to MessengerApp.
        public_rooms : List of public room dicts from the server.
        active_room  : Name of the currently displayed room (str | None).
    """

    def __init__(self, parent: tk.Misc, app, public_rooms: list[dict]) -> None:
        super().__init__(parent, bg="#1e1e2e")
        self.app = app
        self.public_rooms: list[dict] = public_rooms
        self.active_room: str | None = None

        # Keep per-room message widgets so we can hide/show them
        # { room_name: [list of (sender, timestamp, content, type)] }
        self._message_store: dict[str, list[dict]] = {}
        self._member_store: dict[str, list[str]] = {}

        self._build_ui()
        self._populate_room_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the three-column layout."""
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left panel: room list ────────────────────────────────────
        left = tk.Frame(self, bg="#181825", width=180)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        tk.Label(left, text="Rooms", font=("Helvetica", 12, "bold"),
                 bg="#181825", fg="#cdd6f4").pack(pady=(12, 4), padx=8, anchor="w")

        self._room_listbox = tk.Listbox(
            left, bg="#181825", fg="#cdd6f4",
            selectbackground="#313244", selectforeground="#cba6f7",
            font=("Helvetica", 11), relief="flat", bd=0,
            activestyle="none",
        )
        self._room_listbox.pack(fill="both", expand=True, padx=4)
        self._room_listbox.bind("<<ListboxSelect>>", self._on_room_select)

        btn_frame = tk.Frame(left, bg="#181825")
        btn_frame.pack(fill="x", padx=6, pady=6)

        ttk.Button(btn_frame, text="＋ Private room",
                   command=self._create_private_room_dialog).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="✉ Invite user",
                   command=self._invite_user_dialog).pack(fill="x", pady=2)

        # ── Centre panel: messages + input ──────────────────────────
        centre = tk.Frame(self, bg="#1e1e2e")
        centre.grid(row=0, column=1, sticky="nsew")
        centre.rowconfigure(0, weight=1)
        centre.columnconfigure(0, weight=1)

        self._room_title = tk.Label(
            centre, text="Select a room", font=("Helvetica", 13, "bold"),
            bg="#313244", fg="#cdd6f4", anchor="w", padx=12,
        )
        self._room_title.grid(row=0, column=0, sticky="ew", ipady=8)

        self._msg_display = tk.Text(
            centre, state="disabled", wrap="word",
            bg="#1e1e2e", fg="#cdd6f4", font=("Helvetica", 11),
            relief="flat", bd=0, padx=10, pady=10,
        )
        self._msg_display.grid(row=1, column=0, sticky="nsew")
        centre.rowconfigure(1, weight=1)

        scrollbar = ttk.Scrollbar(centre, command=self._msg_display.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self._msg_display.config(yscrollcommand=scrollbar.set)

        # Text colour tags
        self._msg_display.tag_config("sender", foreground="#cba6f7",
                                     font=("Helvetica", 11, "bold"))
        self._msg_display.tag_config("timestamp", foreground="#6c7086",
                                     font=("Helvetica", 9))
        self._msg_display.tag_config("content", foreground="#cdd6f4")
        self._msg_display.tag_config("system", foreground="#a6e3a1",
                                     font=("Helvetica", 10, "italic"))

        # Input row
        input_row = tk.Frame(centre, bg="#313244")
        input_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        input_row.columnconfigure(0, weight=1)

        self._msg_entry = ttk.Entry(input_row, font=("Helvetica", 12))
        self._msg_entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=8,
                             ipady=6)
        self._msg_entry.bind("<Return>", lambda _: self._send_message())

        ttk.Button(input_row, text="Send", command=self._send_message).grid(
            row=0, column=1, padx=4, pady=8)
        ttk.Button(input_row, text="📎", command=self._send_image).grid(
            row=0, column=2, padx=(0, 8), pady=8)

        # ── Right panel: member list ─────────────────────────────────
        right = tk.Frame(self, bg="#181825", width=150)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_propagate(False)

        tk.Label(right, text="Members", font=("Helvetica", 12, "bold"),
                 bg="#181825", fg="#cdd6f4").pack(pady=(12, 4), padx=8, anchor="w")

        self._member_listbox = tk.Listbox(
            right, bg="#181825", fg="#a6e3a1",
            font=("Helvetica", 11), relief="flat", bd=0, activestyle="none",
        )
        self._member_listbox.pack(fill="both", expand=True, padx=4, pady=(0, 8))

    # ------------------------------------------------------------------
    # Room list population
    # ------------------------------------------------------------------

    def _populate_room_list(self) -> None:
        """Fill the left-panel room listbox with available public rooms."""
        for room in self.public_rooms:
            name = room["name"]
            self._room_listbox.insert(tk.END, f"# {name}")
            self._message_store[name] = []
            self._member_store[name] = []

    def _add_room_to_list(self, name: str, private: bool = False) -> None:
        """Insert a new room entry into the listbox."""
        prefix = "🔒" if private else "#"
        self._room_listbox.insert(tk.END, f"{prefix} {name}")
        self._message_store[name] = []
        self._member_store[name] = []

    # ------------------------------------------------------------------
    # Server event dispatcher
    # ------------------------------------------------------------------

    def handle_event(self, event: str, data: dict) -> None:
        """Route a server event to the correct handler method."""
        handlers = {
            "room_joined":     self._on_room_joined,
            "room_created":    self._on_room_created,
            "new_message":     self._on_new_message,
            "user_joined":     self._on_user_joined,
            "user_left":       self._on_user_left,
            "invited_to_room": self._on_invited,
            "error":           self._on_server_error,
        }
        handler = handlers.get(event)
        if handler:
            handler(data)

    # ------------------------------------------------------------------
    # Server event handlers
    # ------------------------------------------------------------------

    def _on_room_joined(self, data: dict) -> None:
        room_name = data["room"]
        self.active_room = room_name
        self._room_title.config(text=f"# {room_name}")

        # Rebuild message display from history
        self._member_store[room_name] = data.get("members", [])
        self._refresh_member_list()

        self._clear_messages()
        for msg in data.get("history", []):
            self._render_message(msg)

    def _on_room_created(self, data: dict) -> None:
        room = data["room"]
        name = room["name"]
        if name not in self._message_store:
            self._add_room_to_list(name, private=True)
        # Auto-join the created room
        self.app.socket.emit("join_room", {"room": name})

    def _on_new_message(self, data: dict) -> None:
        room_name = data.get("room")
        if room_name not in self._message_store:
            self._message_store[room_name] = []
        self._message_store[room_name].append(data)
        # Only render if this is the active room
        if room_name == self.active_room:
            self._render_message(data)

    def _on_user_joined(self, data: dict) -> None:
        room_name = data["room"]
        username = data["username"]
        if room_name not in self._member_store:
            self._member_store[room_name] = []
        if username not in self._member_store[room_name]:
            self._member_store[room_name].append(username)
        if room_name == self.active_room:
            self._refresh_member_list()
            self._append_system(f"{username} joined the room.")

    def _on_user_left(self, data: dict) -> None:
        room_name = data["room"]
        username = data["username"]
        if room_name in self._member_store:
            members = self._member_store[room_name]
            if username in members:
                members.remove(username)
        if room_name == self.active_room:
            self._refresh_member_list()
            self._append_system(f"{username} left the room.")

    def _on_invited(self, data: dict) -> None:
        room_name = data["room"]
        by = data["by"]
        if messagebox.askyesno(
            "Room invitation",
            f"{by} invited you to join '{room_name}'. Join now?"
        ):
            if room_name not in self._message_store:
                self._add_room_to_list(room_name, private=True)
            self.app.socket.emit("join_room", {"room": room_name})

    def _on_server_error(self, data: dict) -> None:
        messagebox.showerror("Server error", data.get("message", "Unknown error"))

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    def _send_message(self) -> None:
        if not self.active_room:
            messagebox.showwarning("No room", "Please join a room first.")
            return
        content = self._msg_entry.get().strip()
        if not content:
            return
        self.app.socket.emit("send_message", {
            "room": self.active_room,
            "content": content,
        })
        self._msg_entry.delete(0, tk.END)

    def _send_image(self) -> None:
        """Open a file dialog, encode the image as base64, send to server."""
        if not self.active_room:
            messagebox.showwarning("No room", "Please join a room first.")
            return
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
        )
        if not path:
            return
        with open(path, "rb") as f:
            raw = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        b64 = base64.b64encode(raw).decode("utf-8")
        image_data = f"data:{mime};base64,{b64}"
        self.app.socket.emit("send_image", {
            "room": self.active_room,
            "image_data": image_data,
            "caption": "",
        })

    # ------------------------------------------------------------------
    # Room selection
    # ------------------------------------------------------------------

    def _on_room_select(self, _event) -> None:
        sel = self._room_listbox.curselection()
        if not sel:
            return
        # Strip the prefix (# or 🔒 ) to get the raw room name
        label: str = self._room_listbox.get(sel[0])
        room_name = label.lstrip("#🔒 ").strip()

        if room_name == self.active_room:
            return

        # If not yet joined, send a join_room event
        if room_name not in self._message_store or not self._member_store.get(room_name):
            self.app.socket.emit("join_room", {"room": room_name})
        else:
            # Already joined — just switch the view locally
            self.active_room = room_name
            self._room_title.config(text=f"# {room_name}")
            self._clear_messages()
            for msg in self._message_store[room_name]:
                self._render_message(msg)
            self._refresh_member_list()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _create_private_room_dialog(self) -> None:
        dialog = _SimpleInputDialog(
            self, title="Create private room", prompt="Room name:"
        )
        name = dialog.result
        if name:
            self.app.socket.emit("create_private_room", {"room": name})

    def _invite_user_dialog(self) -> None:
        if not self.active_room:
            messagebox.showwarning("No room", "Join a private room first.")
            return
        dialog = _SimpleInputDialog(
            self, title="Invite user", prompt="Username to invite:"
        )
        username = dialog.result
        if username:
            self.app.socket.emit("invite_user", {
                "room": self.active_room,
                "target_username": username,
            })

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _clear_messages(self) -> None:
        self._msg_display.config(state="normal")
        self._msg_display.delete("1.0", tk.END)
        self._msg_display.config(state="disabled")

    def _render_message(self, msg: dict) -> None:
        """Append a single message dict to the message display widget."""
        self._msg_display.config(state="normal")
        sender = msg.get("sender", "?")
        ts = msg.get("timestamp", "")
        msg_type = msg.get("type", "TextMessage")

        self._msg_display.insert(tk.END, f"{sender} ", "sender")
        self._msg_display.insert(tk.END, f"[{ts}]\n", "timestamp")

        if msg_type == "TextMessage":
            content = msg.get("content", "")
            self._msg_display.insert(tk.END, f"{content}\n\n", "content")
        elif msg_type == "ImageMessage":
            caption = msg.get("caption", "")
            # Attempt to display the image inline using PhotoImage
            try:
                from PIL import Image, ImageTk  # type: ignore
                image_data: str = msg.get("image_data", "")
                raw = base64.b64decode(image_data.split(",", 1)[1])
                img = Image.open(BytesIO(raw))
                img.thumbnail((300, 300))
                photo = ImageTk.PhotoImage(img)
                # Keep a reference so the image isn't garbage collected
                if not hasattr(self, "_photo_refs"):
                    self._photo_refs = []
                self._photo_refs.append(photo)
                self._msg_display.image_create(tk.END, image=photo)
                self._msg_display.insert(tk.END, "\n")
            except Exception:
                self._msg_display.insert(tk.END, "[image]\n", "content")
            if caption:
                self._msg_display.insert(tk.END, f"{caption}\n", "content")
            self._msg_display.insert(tk.END, "\n")

        self._msg_display.config(state="disabled")
        self._msg_display.see(tk.END)

    def _append_system(self, text: str) -> None:
        """Append a system/status message in green italics."""
        self._msg_display.config(state="normal")
        self._msg_display.insert(tk.END, f"— {text}\n", "system")
        self._msg_display.config(state="disabled")
        self._msg_display.see(tk.END)

    def _refresh_member_list(self) -> None:
        """Rebuild the right-panel member listbox for the active room."""
        self._member_listbox.delete(0, tk.END)
        members = self._member_store.get(self.active_room, [])
        for m in members:
            self._member_listbox.insert(tk.END, f"● {m}")


# ======================================================================
# Small reusable dialog
# ======================================================================

class _SimpleInputDialog(tk.Toplevel):
    """A minimal modal dialog that returns a single text value."""

    def __init__(self, parent, title: str, prompt: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()           # modal
        self.result: str = ""

        tk.Label(self, text=prompt, font=("Helvetica", 11),
                 padx=16, pady=10).pack()
        self._var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self._var, width=28,
                          font=("Helvetica", 11))
        entry.pack(padx=16, pady=(0, 8), ipady=4)
        entry.focus()
        entry.bind("<Return>", lambda _: self._submit())

        ttk.Button(self, text="OK", command=self._submit).pack(pady=(0, 12))
        self.wait_window()        # block until closed

    def _submit(self) -> None:
        self.result = self._var.get().strip()
        self.destroy()
