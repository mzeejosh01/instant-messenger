# server/models/user.py - the User class.
#
# Each user has a connection ID from SocketIO (sid), a username,
# and a list of rooms they have joined.


class User:
    """
    Stores information about one connected user.

    Attributes:
        sid      (str):       the SocketIO connection ID, unique per session
        username (str):       the display name the user picked at login
        rooms    (list[str]): the names of rooms this user has joined
    """

    def __init__(self, sid: str, username: str) -> None:
        self.sid: str = sid
        self.username: str = username
        self.rooms: list[str] = []

    # room membership helpers

    def join_room(self, room_name: str) -> None:
        # add the room to the list if it is not already there
        if room_name not in self.rooms:
            self.rooms.append(room_name)

    def leave_room(self, room_name: str) -> None:
        # remove the room from the list if it is there
        if room_name in self.rooms:
            self.rooms.remove(room_name)

    def to_dict(self) -> dict:
        # return the user data as a plain dictionary
        return {
            "sid": self.sid,
            "username": self.username,
            "rooms": self.rooms,
        }

    def __repr__(self) -> str:
        return f"User(username={self.username!r}, rooms={self.rooms})"
