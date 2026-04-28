"""
server/socket_handler.py - SocketIO event handlers + RoomManager.

RoomManager holds all server state (users and rooms).
register_handlers() wires every SocketIO event to a handler function.

APC requirements met here:
  - list comprehension  : get_all_usernames(), get_public_rooms(), get_history_dicts()
  - filter              : get_user_by_name()
  - map                 : format_member_list() in join_room handler
"""

from flask import request
from flask_socketio import SocketIO, join_room, leave_room, emit

from server.models.user import User
from server.models.message import TextMessage, ImageMessage
from server.models.chatroom import BaseRoom, PublicRoom, PrivateRoom


# ======================================================================
# RoomManager — single instance shared across all handlers
# ======================================================================

class RoomManager:
    """
    Central store for all connected users and active rooms.

    Attributes:
        users (dict[str, User]):     sid  → User
        rooms (dict[str, BaseRoom]): name → Room
    """

    # Public rooms created automatically when the server starts
    DEFAULT_ROOMS: list[str] = ["general", "random"]

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.rooms: dict[str, BaseRoom] = {}

        # Multiple instantiation of PublicRoom (APC requirement)
        for name in self.DEFAULT_ROOMS:
            self.rooms[name] = PublicRoom(name)

    # ------------------------------------------------------------------
    # User helpers
    # ------------------------------------------------------------------

    def add_user(self, sid: str, username: str) -> User:
        user = User(sid, username)
        self.users[sid] = user
        return user

    def remove_user(self, sid: str) -> User | None:
        return self.users.pop(sid, None)

    def get_user(self, sid: str) -> User | None:
        return self.users.get(sid)

    def get_user_by_name(self, username: str) -> User | None:
        """Look up a user by display name.  Uses filter() (APC requirement)."""
        matches = list(filter(lambda u: u.username == username, self.users.values()))
        return matches[0] if matches else None

    def get_all_usernames(self) -> list[str]:
        """Return every connected username.  Uses list comprehension (APC)."""
        return [u.username for u in self.users.values()]

    def is_username_taken(self, username: str) -> bool:
        return username in self.get_all_usernames()

    # ------------------------------------------------------------------
    # Room helpers
    # ------------------------------------------------------------------

    def create_public_room(self, name: str) -> PublicRoom | None:
        if name in self.rooms:
            return None
        room = PublicRoom(name)
        self.rooms[name] = room
        return room

    def create_private_room(self, name: str, owner: str) -> PrivateRoom | None:
        if name in self.rooms:
            return None
        room = PrivateRoom(name, owner)
        self.rooms[name] = room
        return room

    def get_room(self, name: str) -> BaseRoom | None:
        return self.rooms.get(name)

    def get_public_rooms(self) -> list[dict]:
        """Return all PublicRoom metadata dicts.  Uses list comprehension (APC)."""
        return [
            r.to_dict()
            for r in self.rooms.values()
            if isinstance(r, PublicRoom)
        ]


# ======================================================================
# Event handler registration
# ======================================================================

def register_handlers(socketio: SocketIO, manager: RoomManager) -> None:
    """
    Bind all SocketIO events to handler functions.

    Args:
        socketio (SocketIO):    The Flask-SocketIO instance.
        manager  (RoomManager): Shared server state.
    """

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @socketio.on("connect")
    def on_connect():
        print(f"[server] connect   sid={request.sid}")

    @socketio.on("disconnect")
    def on_disconnect():
        user = manager.remove_user(request.sid)
        if not user:
            return
        # Remove the user from every room they were in
        for room_name in user.rooms:
            room = manager.get_room(room_name)
            if room:
                room.remove_member(user.username)
            emit("user_left", {"username": user.username, "room": room_name},
                 to=room_name)
        print(f"[server] disconnect user={user.username}")

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    @socketio.on("login")
    def on_login(data: dict):
        """
        Register a username for this session.

        Client sends:  { "username": str }
        Server emits:
          "login_ok"    → { "username": str, "public_rooms": list[dict] }
          "login_error" → { "message": str }
        """
        username = data.get("username", "").strip()

        if not username:
            emit("login_error", {"message": "Username cannot be empty."})
            return

        if manager.is_username_taken(username):
            emit("login_error", {"message": f"'{username}' is already taken."})
            return

        manager.add_user(request.sid, username)
        emit("login_ok", {
            "username": username,
            "public_rooms": manager.get_public_rooms(),
        })
        print(f"[server] login     user={username}")

    # ------------------------------------------------------------------
    # Joining / leaving rooms
    # ------------------------------------------------------------------

    @socketio.on("join_room")
    def on_join_room(data: dict):
        """
        Client sends:  { "room": str }
        Server emits to caller:
          "room_joined" → { "room": str, "history": list, "members": list[str] }
        Server emits to room (excluding caller):
          "user_joined" → { "username": str, "room": str }
        """
        user = manager.get_user(request.sid)
        if not user:
            emit("error", {"message": "Not logged in."})
            return

        room_name = data.get("room", "").strip()
        room = manager.get_room(room_name)

        if not room:
            emit("error", {"message": f"Room '{room_name}' does not exist."})
            return

        if not room.can_join(user.username):
            emit("error", {"message": f"You are not invited to '{room_name}'."})
            return

        join_room(room_name)
        room.add_member(user.username)
        user.join_room(room_name)

        # Use map() to build a formatted member string list (APC requirement)
        formatted_members = list(map(lambda m: f"• {m}", room.members))

        emit("room_joined", {
            "room": room_name,
            "history": room.get_history_dicts(),
            "members": room.members,
            "members_formatted": formatted_members,
        })
        emit("user_joined",
             {"username": user.username, "room": room_name},
             to=room_name, include_self=False)
        print(f"[server] join_room user={user.username} room={room_name}")

    @socketio.on("leave_room")
    def on_leave_room(data: dict):
        """
        Client sends: { "room": str }
        """
        user = manager.get_user(request.sid)
        if not user:
            return
        room_name = data.get("room", "").strip()
        room = manager.get_room(room_name)
        if room:
            room.remove_member(user.username)
        user.leave_room(room_name)
        leave_room(room_name)
        emit("user_left", {"username": user.username, "room": room_name},
             to=room_name)
        print(f"[server] leave_room user={user.username} room={room_name}")

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    @socketio.on("send_message")
    def on_send_message(data: dict):
        """
        Broadcast a text message to a room.

        Client sends:  { "room": str, "content": str }
        Server emits to room:
          "new_message" → TextMessage.to_dict()
        """
        user = manager.get_user(request.sid)
        if not user:
            emit("error", {"message": "Not logged in."})
            return

        room_name = data.get("room", "")
        content = data.get("content", "").strip()
        if not content:
            return

        room = manager.get_room(room_name)
        if not room:
            emit("error", {"message": f"Room '{room_name}' not found."})
            return

        msg = TextMessage(sender=user.username, room=room_name, content=content)
        room.add_message(msg)
        emit("new_message", msg.to_dict(), to=room_name)

    @socketio.on("send_image")
    def on_send_image(data: dict):
        """
        Broadcast an image message to a room.

        Client sends:  { "room": str, "image_data": str, "caption": str }
        Server emits to room:
          "new_message" → ImageMessage.to_dict()
        """
        user = manager.get_user(request.sid)
        if not user:
            emit("error", {"message": "Not logged in."})
            return

        room_name = data.get("room", "")
        image_data = data.get("image_data", "")
        caption = data.get("caption", "")

        room = manager.get_room(room_name)
        if not room:
            emit("error", {"message": f"Room '{room_name}' not found."})
            return

        msg = ImageMessage(
            sender=user.username,
            room=room_name,
            image_data=image_data,
            caption=caption,
        )
        room.add_message(msg)
        emit("new_message", msg.to_dict(), to=room_name)

    # ------------------------------------------------------------------
    # Private rooms
    # ------------------------------------------------------------------

    @socketio.on("create_private_room")
    def on_create_private_room(data: dict):
        """
        Create a private room and auto-join the creator.

        Client sends:  { "room": str }
        Server emits to caller:
          "room_created" → { "room": dict }
        """
        user = manager.get_user(request.sid)
        if not user:
            return

        room_name = data.get("room", "").strip()
        room = manager.create_private_room(room_name, user.username)

        if not room:
            emit("error", {"message": f"Room '{room_name}' already exists."})
            return

        join_room(room_name)
        room.add_member(user.username)
        user.join_room(room_name)

        emit("room_created", {"room": room.to_dict()})
        print(f"[server] private_room created={room_name} owner={user.username}")

    @socketio.on("invite_user")
    def on_invite_user(data: dict):
        """
        Invite another user to a private room.

        Client sends:  { "room": str, "target_username": str }
        Server emits to target user:
          "invited_to_room" → { "room": str, "by": str }
        Server emits to caller:
          "invite_sent" → { "room": str, "target": str }
        """
        user = manager.get_user(request.sid)
        if not user:
            return

        room_name = data.get("room", "")
        target_name = data.get("target_username", "")

        room = manager.get_room(room_name)
        if not isinstance(room, PrivateRoom):
            emit("error", {"message": "Room is not a private room."})
            return

        if room.owner != user.username:
            emit("error", {"message": "Only the room owner can invite users."})
            return

        target = manager.get_user_by_name(target_name)
        if not target:
            emit("error", {"message": f"User '{target_name}' is not online."})
            return

        room.invite(target_name)
        emit("invited_to_room", {"room": room_name, "by": user.username},
             to=target.sid)
        emit("invite_sent", {"room": room_name, "target": target_name})
        print(f"[server] invite user={target_name} room={room_name}")
