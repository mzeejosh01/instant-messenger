"""
server/models/user.py - User class.

Represents a single connected client. Each user has a SocketIO
session ID (sid), a display name, and a list of joined rooms.
"""


class User:
    """
    Represents a connected chat user.

    Attributes:
        sid      (str):       SocketIO session ID — unique per connection.
        username (str):       Display name chosen at login.
        rooms    (list[str]): Names of rooms this user has joined.
    """

    def __init__(self, sid: str, username: str) -> None:
        self.sid: str = sid
        self.username: str = username
        self.rooms: list[str] = []

    # ------------------------------------------------------------------
    # Room membership helpers
    # ------------------------------------------------------------------

    def join_room(self, room_name: str) -> None:
        """Add *room_name* to this user's room list (no duplicates)."""
        if room_name not in self.rooms:
            self.rooms.append(room_name)

    def leave_room(self, room_name: str) -> None:
        """Remove *room_name* from this user's room list (if present)."""
        if room_name in self.rooms:
            self.rooms.remove(room_name)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this user."""
        return {
            "sid": self.sid,
            "username": self.username,
            "rooms": self.rooms,
        }

    def __repr__(self) -> str:
        return f"User(username={self.username!r}, rooms={self.rooms})"
