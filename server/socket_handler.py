# server/socket_handler.py - handles all SocketIO events from clients.
#
# RoomManager stores all the users and rooms on the server.
# register_handlers() connects each event name to the right function.
#
# APC requirements used here:
#   - list comprehension : get_all_usernames(), get_public_rooms(), get_history_dicts()
#   - filter             : get_user_by_name()
#   - map                : format_member_list() in the join_room handler
#   - inheritance        : PublicRoom and PrivateRoom both extend BaseRoom

from flask import request
from flask_socketio import SocketIO, join_room, leave_room, emit

from server.models.user import User
from server.models.message import TextMessage, ImageMessage
from server.models.chatroom import BaseRoom, PublicRoom, PrivateRoom


class RoomManager:
    """
    Keeps track of all connected users and all active rooms.

    Attributes:
        users (dict): maps each connection ID (sid) to a User object
        rooms (dict): maps each room name to a Room object
    """

    # these two public rooms are created when the server starts
    DEFAULT_ROOMS: list[str] = ["general", "random"]

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.rooms: dict[str, BaseRoom] = {}

        # create the default public rooms (APC requirement: multiple instantiation)
        for name in self.DEFAULT_ROOMS:
            self.rooms[name] = PublicRoom(name)

    # user helper methods

    def add_user(self, sid: str, username: str) -> User:
        user = User(sid, username)
        self.users[sid] = user
        return user

    def remove_user(self, sid: str) -> User | None:
        return self.users.pop(sid, None)

    def get_user(self, sid: str) -> User | None:
        return self.users.get(sid)

    def get_user_by_name(self, username: str) -> User | None:
        # search for a user by their username (APC requirement: filter)
        matches = list(filter(lambda u: u.username == username, self.users.values()))
        return matches[0] if matches else None

    def get_all_usernames(self) -> list[str]:
        # return a list of all connected usernames (APC requirement: list comprehension)
        return [u.username for u in self.users.values()]

    def is_username_taken(self, username: str) -> bool:
        return username in self.get_all_usernames()

    # room helper methods

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
        # return all public rooms as a list of dictionaries (APC requirement: list comprehension)
        return [
            r.to_dict()
            for r in self.rooms.values()
            if isinstance(r, PublicRoom)
        ]


def register_handlers(socketio: SocketIO, manager: RoomManager) -> None:
    # connect each SocketIO event name to its handler function

    # connection events

    @socketio.on("connect")
    def on_connect():
        print(f"[server] connect   sid={request.sid}")

    @socketio.on("disconnect")
    def on_disconnect():
        user = manager.remove_user(request.sid)
        if not user:
            return
        # remove the user from every room they were in
        for room_name in user.rooms:
            room = manager.get_room(room_name)
            if room:
                room.remove_member(user.username)
            emit("user_left", {"username": user.username, "room": room_name},
                 to=room_name)
        print(f"[server] disconnect user={user.username}")
        # send the updated user list to all clients
        socketio.emit("user_list_update", {"users": manager.get_all_usernames()})

    # login

    @socketio.on("login")
    def on_login(data: dict):
        # client sends:  { "username": str }
        # server replies with login_ok or login_error
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
        # send the updated user list to all clients
        socketio.emit("user_list_update", {"users": manager.get_all_usernames()})
        print(f"[server] login     user={username}")

    # joining and leaving rooms

    @socketio.on("join_room")
    def on_join_room(data: dict):
        # client sends:  { "room": str }
        # server sends back the room history and member list
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

        # build a formatted member list (APC requirement: map)
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
        # client sends: { "room": str }
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

    # sending messages

    @socketio.on("send_message")
    def on_send_message(data: dict):
        # client sends:  { "room": str, "content": str }
        # server broadcasts the message to everyone in the room
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
        # client sends:  { "room": str, "image_data": str, "caption": str }
        # server broadcasts the image to everyone in the room
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

    # room creation and invites

    @socketio.on("create_public_room")
    def on_create_public_room(data: dict):
        # client sends:  { "room": str }
        # server tells all connected clients about the new room
        user = manager.get_user(request.sid)
        if not user:
            return

        room_name = data.get("room", "").strip()
        if not room_name:
            emit("error", {"message": "Room name cannot be empty."})
            return

        room = manager.create_public_room(room_name)
        if not room:
            emit("error", {"message": f"Room '{room_name}' already exists."})
            return

        socketio.emit("public_room_created", {"room": room.to_dict()})
        print(f"[server] public_room created={room_name} by={user.username}")

    @socketio.on("create_private_room")
    def on_create_private_room(data: dict):
        # client sends:  { "room": str }
        # server creates the room and auto-joins the creator
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
        # client sends:  { "room": str, "target_username": str }
        # server notifies the target user and confirms to the sender
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
