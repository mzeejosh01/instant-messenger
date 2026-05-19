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

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK   = "#1e1e2e"   # main background
BG_DARKER = "#181825"   # sidebar / panel background
BG_PANEL  = "#313244"   # elevated surfaces (header, input row)
BG_HOVER  = "#2a2a3e"   # room row hover state
BG_ACTIVE = "#45475a"   # selected / active room row
FG_MAIN   = "#cdd6f4"   # primary text
FG_DIM    = "#6c7086"   # secondary text / timestamps
FG_GREEN  = "#a6e3a1"   # member list dots
FG_BLUE   = "#89b4fa"   # online list / own-sender colour
FG_PURPLE = "#cba6f7"   # other-sender colour
FG_RED    = "#f38ba8"   # unread badge background
FG_CYAN   = "#89dceb"   # own message content
ACCENT    = "#cba6f7"   # accent stripe below header


class ChatScreen(tk.Frame):
    """
    Main chat frame shown after a successful login.

    Attributes:
        app          : Reference to MessengerApp.
        public_rooms : List of public room dicts from the server.
        active_room  : Name of the currently displayed room (str | None).
    """

    def __init__(self, parent: tk.Misc, app, public_rooms: list[dict]) -> None:
        super().__init__(parent, bg=BG_DARK)
        self.app = app
        self.public_rooms: list[dict] = public_rooms
        self.active_room: str | None = None

        # Track which rooms this client has actually joined on the server.
        # Fixes the re-join bug: we only emit join_room when not yet in this set.
        self._joined_rooms: set[str] = set()

        # Per-room message and member data
        self._message_store: dict[str, list[dict]] = {}
        self._member_store:  dict[str, list[str]]  = {}

        # Unread badge tracking  { room_name: count }
        self._unread: dict[str, int] = {}

        # Custom room-row widgets  { room_name: Frame }
        self._room_rows:      dict[str, tk.Frame]  = {}
        # Badge canvas per room  { room_name: Canvas }
        self._badge_canvases: dict[str, tk.Canvas] = {}

        # Placeholder state for the message entry
        self._placeholder_active: bool = False

        # Keep PIL ImageTk references alive to avoid garbage-collection
        self._photo_refs: list = []

        self._build_ui()
        self._populate_room_list()
        self._show_welcome_screen()   # start on the welcome screen

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the three-column layout."""
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_left_panel()
        self._build_centre_panel()
        self._build_right_panel()

    # ── Left panel ──────────────────────────────────────────────────────

    def _build_left_panel(self) -> None:
        left = tk.Frame(self, bg=BG_DARKER, width=200)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        # Section label
        tk.Label(
            left, text="ROOMS",
            font=("Helvetica", 9, "bold"), bg=BG_DARKER, fg=FG_DIM,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        # ── Scrollable room list ─────────────────────────────────────
        list_container = tk.Frame(left, bg=BG_DARKER)
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)

        self._room_canvas = tk.Canvas(
            list_container, bg=BG_DARKER, highlightthickness=0, bd=0
        )
        self._room_canvas.grid(row=0, column=0, sticky="nsew")

        room_scroll = ttk.Scrollbar(
            list_container, orient="vertical", command=self._room_canvas.yview
        )
        room_scroll.grid(row=0, column=1, sticky="ns")
        self._room_canvas.configure(yscrollcommand=room_scroll.set)

        self._room_list_inner = tk.Frame(self._room_canvas, bg=BG_DARKER)
        self._cw = self._room_canvas.create_window(
            (0, 0), window=self._room_list_inner, anchor="nw"
        )

        # Keep inner frame width in sync with canvas width
        self._room_list_inner.bind(
            "<Configure>",
            lambda e: self._room_canvas.configure(
                scrollregion=self._room_canvas.bbox("all")
            ),
        )
        self._room_canvas.bind(
            "<Configure>",
            lambda e: self._room_canvas.itemconfig(self._cw, width=e.width),
        )
        # Mouse-wheel scrolling
        self._room_canvas.bind(
            "<MouseWheel>",
            lambda e: self._room_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

        # ── Action buttons ────────────────────────────────────────────
        # Note: we use tk.Label + bindings instead of tk.Button because on
        # macOS the Aqua theme overrides tk.Button's bg, making the text
        # unreadable. tk.Label always renders our colours faithfully.
        btn_frame = tk.Frame(left, bg=BG_DARKER)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=8)

        self._sidebar_btn(btn_frame, "＋ Public room",  self._create_public_room_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "＋ Private room", self._create_private_room_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "✉  Invite user",  self._invite_user_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "← Leave room",   self._leave_room, danger=True).pack(fill="x", pady=2)

    # ── Centre panel ─────────────────────────────────────────────────────

    def _build_centre_panel(self) -> None:
        centre = tk.Frame(self, bg=BG_DARK)
        centre.grid(row=0, column=1, sticky="nsew")
        centre.rowconfigure(1, weight=1)
        centre.columnconfigure(0, weight=1)

        # ── Header bar ───────────────────────────────────────────────
        hdr = tk.Frame(centre, bg=BG_PANEL)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        self._room_title = tk.Label(
            hdr, text="← Select a room",
            font=("Helvetica", 13, "bold"),
            bg=BG_PANEL, fg=FG_MAIN, anchor="w", padx=16, pady=12,
        )
        self._room_title.grid(row=0, column=0, sticky="ew")

        # Member count shown on the right side of the header
        self._member_count_label = tk.Label(
            hdr, text="",
            font=("Helvetica", 10), bg=BG_PANEL, fg=FG_DIM,
            padx=16, pady=12,
        )
        self._member_count_label.grid(row=0, column=1, sticky="e")

        # Accent underline below the header
        tk.Frame(centre, bg=ACCENT, height=2).grid(
            row=0, column=0, columnspan=2, sticky="sew"
        )

        # ── Message area (message display + welcome screen share this slot) ──
        msg_area = tk.Frame(centre, bg=BG_DARK)
        msg_area.grid(row=1, column=0, columnspan=2, sticky="nsew")
        msg_area.rowconfigure(0, weight=1)
        msg_area.columnconfigure(0, weight=1)

        self._msg_display = tk.Text(
            msg_area, state="disabled", wrap="word",
            bg=BG_DARK, fg=FG_MAIN, font=("Helvetica", 11),
            relief="flat", bd=0, padx=16, pady=12,
            spacing1=1, spacing3=1,
        )
        self._msg_display.grid(row=0, column=0, sticky="nsew")

        self._msg_scrollbar = ttk.Scrollbar(msg_area, command=self._msg_display.yview)
        self._msg_scrollbar.grid(row=0, column=1, sticky="ns")
        self._msg_display.config(yscrollcommand=self._msg_scrollbar.set)

        # Welcome screen — occupies the same slot; toggled with the message display
        self._welcome_frame = self._build_welcome_frame(msg_area)
        self._welcome_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Tags for YOUR OWN messages — right-aligned, blue tones
        self._msg_display.tag_config(
            "own_sender", foreground=FG_BLUE,
            font=("Helvetica", 11, "bold"), justify="right")
        self._msg_display.tag_config(
            "own_timestamp", foreground=FG_DIM,
            font=("Helvetica", 9), justify="right")
        self._msg_display.tag_config(
            "own_content", foreground=FG_CYAN,
            justify="right", lmargin1=80, lmargin2=80, spacing3=8)

        # Tags for OTHER PEOPLE'S messages — left-aligned, purple tones
        self._msg_display.tag_config(
            "other_sender", foreground=FG_PURPLE,
            font=("Helvetica", 11, "bold"), justify="left")
        self._msg_display.tag_config(
            "other_timestamp", foreground=FG_DIM,
            font=("Helvetica", 9), justify="left")
        self._msg_display.tag_config(
            "other_content", foreground=FG_MAIN,
            justify="left", spacing3=8)

        # System / status messages — centred, green italic
        self._msg_display.tag_config(
            "system", foreground=FG_GREEN,
            font=("Helvetica", 10, "italic"), justify="center",
            spacing1=6, spacing3=6)

        # ── Input row ────────────────────────────────────────────────
        input_row = tk.Frame(centre, bg=BG_PANEL)
        input_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        input_row.columnconfigure(0, weight=1)

        self._msg_entry = ttk.Entry(input_row, font=("Helvetica", 12))
        self._msg_entry.grid(row=0, column=0, sticky="ew",
                             padx=(12, 6), pady=10, ipady=7)
        self._msg_entry.bind("<Return>", lambda _: self._send_message())
        self._setup_placeholder()

        # Accent-coloured Send button
        tk.Button(
            input_row, text="Send", command=self._send_message,
            font=("Helvetica", 11, "bold"),
            bg=ACCENT, fg=BG_DARK, relief="flat", bd=0,
            padx=16, pady=7, cursor="hand2",
            activebackground="#b48ad4", activeforeground=BG_DARK,
        ).grid(row=0, column=1, padx=4, pady=10)

        tk.Button(
            input_row, text="📎", command=self._send_image,
            font=("Helvetica", 13),
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            padx=8, pady=6, cursor="hand2",
            activebackground=BG_HOVER, activeforeground=FG_MAIN,
        ).grid(row=0, column=2, padx=(0, 12), pady=10)

    def _sidebar_btn(self, parent, text: str, command, danger: bool = False) -> tk.Label:
        """
        Create a reliably-styled sidebar button using tk.Label + click bindings.

        Why not tk.Button? On macOS the Aqua theme overrides bg, rendering
        the button in system style regardless of what colour we set — making
        dark-background buttons unreadable. tk.Label always honours our colours.

        danger=True gives the Leave button a subtle red tint to signal that
        it is a destructive action.
        """
        bg_normal = "#4a1e2a" if danger else "#45475a"   # red-tint vs neutral
        bg_hover  = "#6b2d3e" if danger else "#585b70"
        fg_colour = "#f38ba8" if danger else "#ffffff"

        lbl = tk.Label(
            parent, text=text,
            font=("Helvetica", 10), bg=bg_normal, fg=fg_colour,
            anchor="w", padx=10, pady=7, cursor="hand2",
        )
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>",    lambda _e: lbl.configure(bg=bg_hover))
        lbl.bind("<Leave>",    lambda _e: lbl.configure(bg=bg_normal))
        return lbl

    def _build_welcome_frame(self, parent: tk.Misc) -> tk.Frame:
        """
        Build the welcome / empty-state screen shown before any room is joined.

        Uses place(relx=0.5, rely=0.5) to perfectly centre the content card
        regardless of window size, which is one of the few good uses of
        Tkinter's place geometry manager.
        """
        frame = tk.Frame(parent, bg=BG_DARK)

        # Inner card — centred via place()
        card = tk.Frame(frame, bg=BG_DARK)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # App icon
        tk.Label(
            card, text="💬",
            font=("Helvetica", 52), bg=BG_DARK, fg=ACCENT,
        ).pack(pady=(0, 12))

        # App title
        tk.Label(
            card, text="APC Instant Messenger",
            font=("Helvetica", 20, "bold"), bg=BG_DARK, fg=FG_MAIN,
        ).pack()

        # Personalised welcome line — username is already set by the time
        # ChatScreen is constructed (set in MessengerApp.show_chat before init)
        tk.Label(
            card, text=f"Welcome, {self.app.username}!",
            font=("Helvetica", 13), bg=BG_DARK, fg=FG_DIM,
        ).pack(pady=(6, 20))

        # Divider
        tk.Frame(card, bg=BG_PANEL, height=1, width=340).pack(pady=(0, 18))

        # Usage tips
        tips = [
            ("→", "Select a room from the left panel to start chatting"),
            ("＋", "Create a public room to open a new channel for everyone"),
            ("🔒", "Create a private room for invite-only conversations"),
            ("✉", "Invite a user to a private room by their username"),
            ("📎", "Send images directly into any room chat"),
        ]
        for icon, tip_text in tips:
            row = tk.Frame(card, bg=BG_DARK)
            row.pack(fill="x", pady=3, anchor="w")
            tk.Label(
                row, text=icon,
                font=("Helvetica", 11), bg=BG_DARK, fg=ACCENT, width=3,
            ).pack(side="left")
            tk.Label(
                row, text=tip_text,
                font=("Helvetica", 11), bg=BG_DARK, fg=FG_DIM, anchor="w",
            ).pack(side="left")

        # Footer status line
        tk.Frame(card, bg=BG_PANEL, height=1, width=340).pack(pady=(20, 10))
        tk.Label(
            card, text="● Connected and ready",
            font=("Helvetica", 10), bg=BG_DARK, fg=FG_GREEN,
        ).pack()

        return frame

    def _show_welcome_screen(self) -> None:
        """Hide the message display and show the welcome frame."""
        self._msg_display.grid_remove()
        self._msg_scrollbar.grid_remove()
        self._welcome_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def _hide_welcome_screen(self) -> None:
        """Hide the welcome frame and restore the message display."""
        self._welcome_frame.grid_remove()
        self._msg_display.grid(row=0, column=0, sticky="nsew")
        self._msg_scrollbar.grid(row=0, column=1, sticky="ns")

    def _setup_placeholder(self) -> None:
        """Add a dim placeholder hint to the message entry."""
        _ph = "Type a message…"

        def _focus_in(_e):
            if self._placeholder_active:
                self._msg_entry.delete(0, tk.END)
                self._msg_entry.config(foreground=FG_MAIN)
                self._placeholder_active = False

        def _focus_out(_e):
            if not self._msg_entry.get():
                self._msg_entry.insert(0, _ph)
                self._msg_entry.config(foreground=FG_DIM)
                self._placeholder_active = True

        self._msg_entry.insert(0, _ph)
        self._msg_entry.config(foreground=FG_DIM)
        self._placeholder_active = True
        self._msg_entry.bind("<FocusIn>",  _focus_in)
        self._msg_entry.bind("<FocusOut>", _focus_out)

    # ── Right panel ───────────────────────────────────────────────────────

    def _build_right_panel(self) -> None:
        right = tk.Frame(self, bg=BG_DARKER, width=160)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_propagate(False)

        tk.Label(
            right, text="MEMBERS",
            font=("Helvetica", 9, "bold"), bg=BG_DARKER, fg=FG_DIM,
        ).pack(pady=(14, 6), padx=12, anchor="w")

        self._member_listbox = tk.Listbox(
            right, bg=BG_DARKER, fg=FG_GREEN,
            font=("Helvetica", 10), relief="flat", bd=0,
            activestyle="none", selectbackground=BG_DARKER,
        )
        self._member_listbox.pack(fill="x", padx=8, pady=(0, 4))

        tk.Frame(right, bg=BG_PANEL, height=1).pack(fill="x", padx=8, pady=8)

        tk.Label(
            right, text="ONLINE",
            font=("Helvetica", 9, "bold"), bg=BG_DARKER, fg=FG_DIM,
        ).pack(pady=(0, 6), padx=12, anchor="w")

        self._online_listbox = tk.Listbox(
            right, bg=BG_DARKER, fg=FG_BLUE,
            font=("Helvetica", 10), relief="flat", bd=0,
            activestyle="none", selectbackground=BG_DARKER,
            height=6,
        )
        self._online_listbox.pack(fill="x", padx=8, pady=(0, 8))

    # ------------------------------------------------------------------
    # Room list – custom rows with badge support
    # ------------------------------------------------------------------

    def _populate_room_list(self) -> None:
        """Fill the left-panel room list with available public rooms."""
        for room in self.public_rooms:
            name = room["name"]
            self._message_store[name] = []
            self._member_store[name]  = []
            self._unread[name] = 0
            self._make_room_row(name, private=False)

    def _add_room_to_list(self, name: str, private: bool = False) -> None:
        """Insert a new room row into the scrollable list."""
        if name not in self._message_store:
            self._message_store[name] = []
            self._member_store[name]  = []
            self._unread[name] = 0
            self._make_room_row(name, private=private)

    def _make_room_row(self, name: str, private: bool = False) -> None:
        """
        Create a clickable room row with a red unread-badge slot.

        Each row is a tk.Frame containing:
          - a Label with the room name (expands to fill available width)
          - a small Canvas that draws a red oval badge (hidden when count == 0)
        """
        prefix = "🔒" if private else "#"

        row = tk.Frame(self._room_list_inner, bg=BG_DARKER, cursor="hand2")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)

        name_lbl = tk.Label(
            row, text=f"  {prefix} {name}",
            bg=BG_DARKER, fg=FG_MAIN,
            font=("Helvetica", 11), anchor="w",
            pady=8, padx=4,
        )
        name_lbl.grid(row=0, column=0, sticky="ew")

        # Badge canvas — draws a red oval with white count text
        badge = tk.Canvas(
            row, width=24, height=18,
            bg=BG_DARKER, highlightthickness=0,
        )
        badge.grid(row=0, column=1, padx=(0, 8))
        badge.grid_remove()   # hidden until there are unread messages

        self._room_rows[name]      = row
        self._badge_canvases[name] = badge

        # Click → select this room
        for w in (row, name_lbl, badge):
            w.bind("<Button-1>", lambda _e, r=name: self._select_room(r))

        # Hover effects (skip when this is the active room)
        def _enter(_e, r=name):
            if r != self.active_room:
                self._set_row_bg(r, BG_HOVER)

        def _leave(_e, r=name):
            if r != self.active_room:
                self._set_row_bg(r, BG_DARKER)

        for w in (row, name_lbl, badge):
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

    def _set_row_bg(self, room_name: str, colour: str) -> None:
        """Set the background of a room row and all its child widgets."""
        row = self._room_rows.get(room_name)
        if not row:
            return
        row.configure(bg=colour)
        for w in row.winfo_children():
            try:
                w.configure(bg=colour)
            except tk.TclError:
                pass

    def _update_badge(self, room_name: str) -> None:
        """
        Redraw the unread badge for a room.
        Shows a red oval with a white count number; hides when count is 0.
        """
        count = self._unread.get(room_name, 0)
        badge = self._badge_canvases.get(room_name)
        if badge is None:
            return
        badge.delete("all")
        if count > 0:
            badge.grid()   # make visible
            label = str(count) if count < 100 else "99+"
            badge.create_oval(1, 1, 23, 17, fill=FG_RED, outline="")
            badge.create_text(12, 9, text=label, fill="white",
                              font=("Helvetica", 8, "bold"))
        else:
            badge.grid_remove()   # hide

    # ------------------------------------------------------------------
    # Room selection
    # ------------------------------------------------------------------

    def _select_room(self, room_name: str) -> None:
        """Handle clicking on a room row in the left panel."""
        if room_name == self.active_room:
            return

        # De-highlight previously active room
        if self.active_room:
            self._set_row_bg(self.active_room, BG_DARKER)

        # Highlight the newly selected room
        self._set_row_bg(room_name, BG_ACTIVE)

        # Clear the unread badge immediately on selection
        self._unread[room_name] = 0
        self._update_badge(room_name)

        if room_name in self._joined_rooms:
            # Already joined on the server — switch the view locally only
            self._hide_welcome_screen()
            self.active_room = room_name
            self._room_title.config(text=f"# {room_name}")
            self._update_member_count()
            self._clear_messages()
            for msg in self._message_store[room_name]:
                self._render_message(msg)
            self._refresh_member_list()
        else:
            # Not yet joined — ask the server to add us
            self.app.socket.emit("join_room", {"room": room_name})

    # ------------------------------------------------------------------
    # Server event dispatcher
    # ------------------------------------------------------------------

    def handle_event(self, event: str, data: dict) -> None:
        """Route a server event to the correct handler method."""
        handlers = {
            "room_joined":         self._on_room_joined,
            "room_created":        self._on_room_created,
            "new_message":         self._on_new_message,
            "user_joined":         self._on_user_joined,
            "user_left":           self._on_user_left,
            "invited_to_room":     self._on_invited,
            "invite_sent":         self._on_invite_sent,
            "user_list_update":    self._on_user_list_update,
            "public_room_created": self._on_public_room_created,
            "error":               self._on_server_error,
        }
        handler = handlers.get(event)
        if handler:
            handler(data)

    # ------------------------------------------------------------------
    # Server event handlers
    # ------------------------------------------------------------------

    def _on_room_joined(self, data: dict) -> None:
        room_name = data["room"]
        self._joined_rooms.add(room_name)

        # De-highlight the old active room
        if self.active_room and self.active_room != room_name:
            self._set_row_bg(self.active_room, BG_DARKER)

        self.active_room = room_name
        self._message_store[room_name] = data.get("history", [])
        self._member_store[room_name]  = data.get("members", [])

        # Highlight new room + clear its badge
        self._unread[room_name] = 0
        self._update_badge(room_name)
        self._set_row_bg(room_name, BG_ACTIVE)

        self._hide_welcome_screen()   # switch from welcome to message view
        self._room_title.config(text=f"# {room_name}")
        self._update_member_count()
        self._refresh_member_list()
        self._clear_messages()
        for msg in self._message_store[room_name]:
            self._render_message(msg)

    def _on_room_created(self, data: dict) -> None:
        room = data["room"]
        name = room["name"]
        if name not in self._message_store:
            self._add_room_to_list(name, private=True)
        # Auto-join the room the user just created
        self.app.socket.emit("join_room", {"room": name})

    def _on_new_message(self, data: dict) -> None:
        room_name = data.get("room")
        if room_name not in self._message_store:
            self._message_store[room_name] = []
        if room_name not in self._unread:
            self._unread[room_name] = 0
        self._message_store[room_name].append(data)

        if room_name == self.active_room:
            # Room is open — render immediately
            self._render_message(data)
        else:
            # Room is in the background — increment the unread badge
            self._unread[room_name] += 1
            self._update_badge(room_name)

    def _on_user_joined(self, data: dict) -> None:
        room_name = data["room"]
        username  = data["username"]
        if room_name not in self._member_store:
            self._member_store[room_name] = []
        if username not in self._member_store[room_name]:
            self._member_store[room_name].append(username)
        if room_name == self.active_room:
            self._refresh_member_list()
            self._update_member_count()
            self._append_system(f"{username} joined the room.")

    def _on_user_left(self, data: dict) -> None:
        room_name = data["room"]
        username  = data["username"]
        if room_name in self._member_store and username in self._member_store[room_name]:
            self._member_store[room_name].remove(username)
        if room_name == self.active_room:
            self._refresh_member_list()
            self._update_member_count()
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

    def _on_invite_sent(self, data: dict) -> None:
        """Confirm to the inviter that their invite was delivered."""
        target = data.get("target", "")
        room   = data.get("room", "")
        messagebox.showinfo("Invite sent", f"Invited {target} to '{room}'.")

    def _on_user_list_update(self, data: dict) -> None:
        """Refresh the Online panel whenever someone joins or leaves."""
        users = data.get("users", [])
        self._online_listbox.delete(0, tk.END)
        # Use list comprehension to build display strings (APC requirement)
        display = [f"● {u}" for u in users]
        for entry in display:
            self._online_listbox.insert(tk.END, entry)

    def _on_public_room_created(self, data: dict) -> None:
        """Add a newly created public room to the room list."""
        room = data["room"]
        name = room["name"]
        if name not in self._message_store:
            self._add_room_to_list(name, private=False)

    # ------------------------------------------------------------------
    # Sending messages
    # ------------------------------------------------------------------

    def _send_message(self) -> None:
        if not self.active_room:
            messagebox.showwarning("No room", "Please join a room first.")
            return
        if self._placeholder_active:
            return
        content = self._msg_entry.get().strip()
        if not content:
            return
        self.app.socket.emit("send_message", {
            "room":    self.active_room,
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
        ext  = path.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        b64  = base64.b64encode(raw).decode("utf-8")
        self.app.socket.emit("send_image", {
            "room":       self.active_room,
            "image_data": f"data:{mime};base64,{b64}",
            "caption":    "",
        })

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _create_public_room_dialog(self) -> None:
        dialog = _SimpleInputDialog(self, title="Create public room", prompt="Room name:")
        if dialog.result:
            self.app.socket.emit("create_public_room", {"room": dialog.result})

    def _create_private_room_dialog(self) -> None:
        dialog = _SimpleInputDialog(self, title="Create private room", prompt="Room name:")
        if dialog.result:
            self.app.socket.emit("create_private_room", {"room": dialog.result})

    def _leave_room(self) -> None:
        """Leave the currently active room."""
        if not self.active_room:
            messagebox.showwarning("No room", "You are not in a room.")
            return
        leaving = self.active_room
        self.app.socket.emit("leave_room", {"room": leaving})
        self._joined_rooms.discard(leaving)
        self._message_store[leaving] = []
        self._member_store[leaving]  = []
        self._unread[leaving] = 0
        self._update_badge(leaving)
        self._set_row_bg(leaving, BG_DARKER)
        self.active_room = None
        self._room_title.config(text="← Select a room")
        self._member_count_label.config(text="")
        self._clear_messages()
        self._refresh_member_list()
        self._show_welcome_screen()   # return to the welcome screen

    def _invite_user_dialog(self) -> None:
        if not self.active_room:
            messagebox.showwarning("No room", "Join a private room first.")
            return
        dialog = _SimpleInputDialog(self, title="Invite user", prompt="Username to invite:")
        if dialog.result:
            self.app.socket.emit("invite_user", {
                "room":            self.active_room,
                "target_username": dialog.result,
            })

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _update_member_count(self) -> None:
        """Update the member count label in the header bar."""
        count = len(self._member_store.get(self.active_room, []))
        noun  = "member" if count == 1 else "members"
        self._member_count_label.config(text=f"👥 {count} {noun}")

    def _clear_messages(self) -> None:
        self._msg_display.config(state="normal")
        self._msg_display.delete("1.0", tk.END)
        self._msg_display.config(state="disabled")

    def _render_message(self, msg: dict) -> None:
        """Append a single message dict to the message display widget."""
        self._msg_display.config(state="normal")
        sender   = msg.get("sender", "?")
        ts       = msg.get("timestamp", "")
        msg_type = msg.get("type", "TextMessage")

        # Choose tag set based on whether this is our own message
        is_own = (sender == self.app.username)
        s_tag, ts_tag, c_tag = (
            ("own_sender",   "own_timestamp",   "own_content")   if is_own else
            ("other_sender", "other_timestamp", "other_content")
        )

        self._msg_display.insert(tk.END, f"{sender} ", s_tag)
        self._msg_display.insert(tk.END, f"[{ts}]\n", ts_tag)

        if msg_type == "TextMessage":
            content = msg.get("content", "")
            self._msg_display.insert(tk.END, f"{content}\n\n", c_tag)

        elif msg_type == "ImageMessage":
            caption = msg.get("caption", "")
            try:
                from PIL import Image, ImageTk  # type: ignore
                image_data: str = msg.get("image_data", "")
                raw   = base64.b64decode(image_data.split(",", 1)[1])
                img   = Image.open(BytesIO(raw))
                img.thumbnail((300, 300))
                photo = ImageTk.PhotoImage(img)
                self._photo_refs.append(photo)
                self._msg_display.image_create(tk.END, image=photo)
                self._msg_display.insert(tk.END, "\n")
            except Exception:
                self._msg_display.insert(tk.END, "[image]\n", c_tag)
            if caption:
                self._msg_display.insert(tk.END, f"{caption}\n", c_tag)
            self._msg_display.insert(tk.END, "\n")

        self._msg_display.config(state="disabled")
        self._msg_display.see(tk.END)

    def _append_system(self, text: str) -> None:
        """Append a system/status message in green italics, centred."""
        self._msg_display.config(state="normal")
        self._msg_display.insert(tk.END, f"— {text} —\n", "system")
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
        self.configure(bg=BG_DARKER)
        self.resizable(False, False)
        self.grab_set()           # modal
        self.result: str = ""

        tk.Label(
            self, text=prompt,
            font=("Helvetica", 11), bg=BG_DARKER, fg=FG_MAIN,
            padx=20, pady=14,
        ).pack()

        self._var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self._var, width=28,
                          font=("Helvetica", 11))
        entry.pack(padx=20, pady=(0, 10), ipady=5)
        entry.focus()
        entry.bind("<Return>", lambda _: self._submit())

        tk.Button(
            self, text="  OK  ", command=self._submit,
            font=("Helvetica", 11, "bold"),
            bg=ACCENT, fg=BG_DARK, relief="flat", bd=0,
            padx=16, pady=6, cursor="hand2",
            activebackground="#b48ad4", activeforeground=BG_DARK,
        ).pack(pady=(0, 16))

        self.wait_window()        # block until closed

    def _submit(self) -> None:
        self.result = self._var.get().strip()
        self.destroy()
