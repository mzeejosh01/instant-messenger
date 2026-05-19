# client/chat_screen.py - the main chat window shown after login.
#
# Layout:
#   left panel   - list of rooms the user can join
#   centre panel - message history and the input box
#   right panel  - list of members and online users
#
# All server events come in through handle_event().

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import base64
from io import BytesIO

# colour palette used across the whole chat screen
BG_DARK   = "#1e1e2e"   # main background
BG_DARKER = "#181825"   # sidebar background
BG_PANEL  = "#313244"   # header and input bar
BG_HOVER  = "#2a2a3e"   # room row when hovered
BG_ACTIVE = "#45475a"   # currently selected room row
FG_MAIN   = "#cdd6f4"   # main text colour
FG_DIM    = "#6c7086"   # dim text for timestamps etc.
FG_GREEN  = "#a6e3a1"   # member list dots
FG_BLUE   = "#89b4fa"   # online list and own message name
FG_PURPLE = "#cba6f7"   # other people's message name
FG_RED    = "#f38ba8"   # unread badge
FG_CYAN   = "#89dceb"   # own message text
ACCENT    = "#cba6f7"   # accent line under the header


class ChatScreen(tk.Frame):
    """
    The main chat frame shown after login.

    Attributes:
        app          : reference to MessengerApp
        public_rooms : list of public room dicts from the server
        active_room  : name of the room currently open (or None)
    """

    def __init__(self, parent: tk.Misc, app, public_rooms: list[dict]) -> None:
        super().__init__(parent, bg=BG_DARK)
        self.app = app
        self.public_rooms: list[dict] = public_rooms
        self.active_room: str | None = None

        # set of room names we have already joined on the server
        # we only emit join_room if the room is not in this set
        self._joined_rooms: set[str] = set()

        # message and member lists stored per room
        self._message_store: dict[str, list[dict]] = {}
        self._member_store:  dict[str, list[str]]  = {}

        # how many unread messages each room has
        self._unread: dict[str, int] = {}

        # the Frame widget for each room row in the sidebar
        self._room_rows:      dict[str, tk.Frame]  = {}
        # the Canvas badge widget for each room
        self._badge_canvases: dict[str, tk.Canvas] = {}

        # tracks whether the placeholder text is currently showing
        self._placeholder_active: bool = False

        # keep image references here so Python does not delete them
        self._photo_refs: list = []

        self._build_ui()
        self._populate_room_list()
        self._show_welcome_screen()   # start on the welcome screen

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # build the three-column layout
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_left_panel()
        self._build_centre_panel()
        self._build_right_panel()

    # left panel

    def _build_left_panel(self) -> None:
        left = tk.Frame(self, bg=BG_DARKER, width=200)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        # section heading
        tk.Label(
            left, text="ROOMS",
            font=("Helvetica", 9, "bold"), bg=BG_DARKER, fg=FG_DIM,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        # scrollable list of rooms
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

        # keep the inner frame the same width as the canvas
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
        # scroll with the mouse wheel
        self._room_canvas.bind(
            "<MouseWheel>",
            lambda e: self._room_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

        # sidebar buttons
        # we use tk.Label instead of tk.Button because on macOS, tk.Button
        # ignores our background colour setting, but tk.Label always shows it
        btn_frame = tk.Frame(left, bg=BG_DARKER)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=8)

        self._sidebar_btn(btn_frame, "＋ Public room",  self._create_public_room_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "＋ Private room", self._create_private_room_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "✉  Invite user",  self._invite_user_dialog).pack(fill="x", pady=2)
        self._sidebar_btn(btn_frame, "← Leave room",   self._leave_room, danger=True).pack(fill="x", pady=2)

    # centre panel

    def _build_centre_panel(self) -> None:
        centre = tk.Frame(self, bg=BG_DARK)
        centre.grid(row=0, column=1, sticky="nsew")
        centre.rowconfigure(1, weight=1)
        centre.columnconfigure(0, weight=1)

        # header bar at the top of the centre panel
        hdr = tk.Frame(centre, bg=BG_PANEL)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        self._room_title = tk.Label(
            hdr, text="← Select a room",
            font=("Helvetica", 13, "bold"),
            bg=BG_PANEL, fg=FG_MAIN, anchor="w", padx=16, pady=12,
        )
        self._room_title.grid(row=0, column=0, sticky="ew")

        # member count label on the right side of the header
        self._member_count_label = tk.Label(
            hdr, text="",
            font=("Helvetica", 10), bg=BG_PANEL, fg=FG_DIM,
            padx=16, pady=12,
        )
        self._member_count_label.grid(row=0, column=1, sticky="e")

        # thin accent line below the header
        tk.Frame(centre, bg=ACCENT, height=2).grid(
            row=0, column=0, columnspan=2, sticky="sew"
        )

        # message area - both the chat display and welcome screen go in this slot
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

        # welcome screen sits in the same slot and is shown when no room is open
        self._welcome_frame = self._build_welcome_frame(msg_area)
        self._welcome_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # tags for your own messages - right side, blue
        self._msg_display.tag_config(
            "own_sender", foreground=FG_BLUE,
            font=("Helvetica", 11, "bold"), justify="right")
        self._msg_display.tag_config(
            "own_timestamp", foreground=FG_DIM,
            font=("Helvetica", 9), justify="right")
        self._msg_display.tag_config(
            "own_content", foreground=FG_CYAN,
            justify="right", lmargin1=80, lmargin2=80, spacing3=8)

        # tags for other people's messages - left side, purple
        self._msg_display.tag_config(
            "other_sender", foreground=FG_PURPLE,
            font=("Helvetica", 11, "bold"), justify="left")
        self._msg_display.tag_config(
            "other_timestamp", foreground=FG_DIM,
            font=("Helvetica", 9), justify="left")
        self._msg_display.tag_config(
            "other_content", foreground=FG_MAIN,
            justify="left", spacing3=8)

        # tags for system messages like "user joined"
        self._msg_display.tag_config(
            "system", foreground=FG_GREEN,
            font=("Helvetica", 10, "italic"), justify="center",
            spacing1=6, spacing3=6)

        # input row at the bottom of the centre panel
        self._input_row = tk.Frame(centre, bg=BG_PANEL)
        self._input_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._input_row.columnconfigure(0, weight=1)

        self._msg_entry = ttk.Entry(self._input_row, font=("Helvetica", 12))
        self._msg_entry.grid(row=0, column=0, sticky="ew",
                             padx=(12, 6), pady=10, ipady=7)
        self._msg_entry.bind("<Return>", lambda _: self._send_message())
        self._setup_placeholder()

        # send button
        tk.Button(
            self._input_row, text="Send", command=self._send_message,
            font=("Helvetica", 11, "bold"),
            bg=ACCENT, fg=BG_DARK, relief="flat", bd=0,
            padx=16, pady=7, cursor="hand2",
            activebackground="#b48ad4", activeforeground=BG_DARK,
        ).grid(row=0, column=1, padx=4, pady=10)

        # image upload button
        tk.Button(
            self._input_row, text="📎", command=self._send_image,
            font=("Helvetica", 13),
            bg=BG_PANEL, fg=FG_MAIN, relief="flat", bd=0,
            padx=8, pady=6, cursor="hand2",
            activebackground=BG_HOVER, activeforeground=FG_MAIN,
        ).grid(row=0, column=2, padx=(0, 12), pady=10)

    def _sidebar_btn(self, parent, text: str, command, danger: bool = False) -> tk.Label:
        # create a sidebar button using tk.Label with click and hover bindings
        # danger=True makes the Leave button red to show it is a risky action
        bg_normal = "#4a1e2a" if danger else "#45475a"
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
        # build the welcome screen shown when no room is open
        frame = tk.Frame(parent, bg=BG_DARK)

        # place the card in the centre of the frame
        card = tk.Frame(frame, bg=BG_DARK)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # app icon and title
        tk.Label(
            card, text="💬",
            font=("Helvetica", 52), bg=BG_DARK, fg=ACCENT,
        ).pack(pady=(0, 12))

        tk.Label(
            card, text="APC Instant Messenger",
            font=("Helvetica", 20, "bold"), bg=BG_DARK, fg=FG_MAIN,
        ).pack()

        # username is already set in MessengerApp.show_chat before this runs
        tk.Label(
            card, text=f"Welcome, {self.app.username}!",
            font=("Helvetica", 13), bg=BG_DARK, fg=FG_DIM,
        ).pack(pady=(6, 20))

        tk.Frame(card, bg=BG_PANEL, height=1, width=340).pack(pady=(0, 18))

        # tips to help the user get started
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

        # status line at the bottom of the welcome card
        tk.Frame(card, bg=BG_PANEL, height=1, width=340).pack(pady=(20, 10))
        tk.Label(
            card, text="● Connected and ready",
            font=("Helvetica", 10), bg=BG_DARK, fg=FG_GREEN,
        ).pack()

        return frame

    def _show_welcome_screen(self) -> None:
        """Show the welcome page and hide the chat area and input row."""
        self._msg_display.grid_remove()
        self._msg_scrollbar.grid_remove()
        self._input_row.grid_remove()
        self._welcome_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

    def _hide_welcome_screen(self) -> None:
        """Hide the welcome page and bring back the chat area and input row."""
        self._welcome_frame.grid_remove()
        self._msg_display.grid(row=0, column=0, sticky="nsew")
        self._msg_scrollbar.grid(row=0, column=1, sticky="ns")
        self._input_row.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _setup_placeholder(self) -> None:
        # add dim placeholder text to the message entry field
        _ph = "Type a message..."

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

    # right panel

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

    # room list

    def _populate_room_list(self) -> None:
        # fill the room list with the public rooms received at login
        for room in self.public_rooms:
            name = room["name"]
            self._message_store[name] = []
            self._member_store[name]  = []
            self._unread[name] = 0
            self._make_room_row(name, private=False)

    def _add_room_to_list(self, name: str, private: bool = False) -> None:
        # add a new room row to the sidebar list
        if name not in self._message_store:
            self._message_store[name] = []
            self._member_store[name]  = []
            self._unread[name] = 0
            self._make_room_row(name, private=private)

    def _make_room_row(self, name: str, private: bool = False) -> None:
        # create one room row with a name label and an unread badge
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

        # badge canvas that shows a red dot with the unread count
        badge = tk.Canvas(
            row, width=24, height=18,
            bg=BG_DARKER, highlightthickness=0,
        )
        badge.grid(row=0, column=1, padx=(0, 8))
        badge.grid_remove()   # hidden until there are unread messages

        self._room_rows[name]      = row
        self._badge_canvases[name] = badge

        # clicking anywhere on the row selects that room
        for w in (row, name_lbl, badge):
            w.bind("<Button-1>", lambda _e, r=name: self._select_room(r))

        # hover highlight (only when the room is not already selected)
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
        # change the background colour of a room row and all its children
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
        # redraw the unread badge for a room, or hide it if count is 0
        count = self._unread.get(room_name, 0)
        badge = self._badge_canvases.get(room_name)
        if badge is None:
            return
        badge.delete("all")
        if count > 0:
            badge.grid()   # show the badge
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
        # called when the user clicks on a room in the sidebar
        if room_name == self.active_room:
            return

        # remove the highlight from the previous room
        if self.active_room:
            self._set_row_bg(self.active_room, BG_DARKER)

        # highlight the newly selected room
        self._set_row_bg(room_name, BG_ACTIVE)

        # clear the unread badge right away
        self._unread[room_name] = 0
        self._update_badge(room_name)

        if room_name in self._joined_rooms:
            # we already joined this room before, just switch the view locally
            self._hide_welcome_screen()
            self.active_room = room_name
            self._room_title.config(text=f"# {room_name}")
            self._update_member_count()
            self._clear_messages()
            for msg in self._message_store[room_name]:
                self._render_message(msg)
            self._refresh_member_list()
        else:
            # not joined yet, ask the server to add us
            self.app.socket.emit("join_room", {"room": room_name})

    # ------------------------------------------------------------------
    # Server event dispatcher
    # ------------------------------------------------------------------

    def handle_event(self, event: str, data: dict) -> None:
        # send each server event to the right handler method
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
        # auto-join the room after creating it
        self.app.socket.emit("join_room", {"room": name})

    def _on_new_message(self, data: dict) -> None:
        room_name = data.get("room")
        if room_name not in self._message_store:
            self._message_store[room_name] = []
        if room_name not in self._unread:
            self._unread[room_name] = 0
        self._message_store[room_name].append(data)

        if room_name == self.active_room:
            # room is open, show the message right away
            self._render_message(data)
        else:
            # room is in the background, just update the badge count
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
        # show a message to confirm the invite was sent
        target = data.get("target", "")
        room   = data.get("room", "")
        messagebox.showinfo("Invite sent", f"Invited {target} to '{room}'.")

    def _on_user_list_update(self, data: dict) -> None:
        # rebuild the Online list every time someone connects or disconnects
        users = data.get("users", [])
        self._online_listbox.delete(0, tk.END)
        # build the display strings with a list comprehension (APC requirement)
        display = [f"● {u}" for u in users]
        for entry in display:
            self._online_listbox.insert(tk.END, entry)

    def _on_public_room_created(self, data: dict) -> None:
        # add the new public room to the sidebar if it is not there yet
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
        # open a file picker, encode the image as base64 and send it
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
        # leave the current room and go back to the welcome screen
        if not self.active_room:
            messagebox.showwarning("No room", "You are not in a room.")
            return
        leaving = self.active_room
        self.app.socket.emit("leave_room", {"room": leaving})
        self._joined_rooms.discard(leaving)
        self._message_store[leaving] = []  # clear stored messages
        self._member_store[leaving]  = []
        self._unread[leaving] = 0
        self._update_badge(leaving)
        self._set_row_bg(leaving, BG_DARKER)
        self.active_room = None
        self._room_title.config(text="<- Select a room")
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
        # update the member count shown in the header
        count = len(self._member_store.get(self.active_room, []))
        noun  = "member" if count == 1 else "members"
        self._member_count_label.config(text=f"👥 {count} {noun}")

    def _clear_messages(self) -> None:
        self._msg_display.config(state="normal")
        self._msg_display.delete("1.0", tk.END)
        self._msg_display.config(state="disabled")

    def _render_message(self, msg: dict) -> None:
        # add one message to the chat display
        self._msg_display.config(state="normal")
        sender   = msg.get("sender", "?")
        ts       = msg.get("timestamp", "")
        msg_type = msg.get("type", "TextMessage")

        # use different tags depending on whether we sent this message
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
        # add a system message like "user joined" in green italic text
        self._msg_display.config(state="normal")
        self._msg_display.insert(tk.END, f"— {text} —\n", "system")
        self._msg_display.config(state="disabled")
        self._msg_display.see(tk.END)

    def _refresh_member_list(self) -> None:
        # rebuild the member list for the currently open room
        self._member_listbox.delete(0, tk.END)
        members = self._member_store.get(self.active_room, [])
        for m in members:
            self._member_listbox.insert(tk.END, f"● {m}")


# ======================================================================
# Small reusable dialog
# ======================================================================

class _SimpleInputDialog(tk.Toplevel):
    """A small pop-up dialog that asks the user to type something."""

    def __init__(self, parent, title: str, prompt: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG_DARKER)
        self.resizable(False, False)
        self.grab_set()           # make it modal so you have to close it first
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

        self.wait_window()        # wait until the user closes the dialog

    def _submit(self) -> None:
        self.result = self._var.get().strip()
        self.destroy()
