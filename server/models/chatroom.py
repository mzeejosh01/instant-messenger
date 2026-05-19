# server/models/chatroom.py - room classes.
#
# BaseRoom is the parent class.
# PublicRoom and PrivateRoom both inherit from it.
# PublicRoom is open to everyone. PrivateRoom is invite-only.
# We use inheritance because all rooms share the same basic behaviour.

from __future__ import annotations
from server.models.message import BaseMessage


class BaseRoom:
    """
    Parent class for all room types.

    Attributes:
        name    (str):               the unique name of the room
        members (list[str]):         usernames of people currently in the room
        history (list[BaseMessage]): all messages sent in the room so far
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.members: list[str] = []
        self.history: list[BaseMessage] = []

    # membership methods

    def add_member(self, username: str) -> None:
        # add the user only if they are not already in the room
        if username not in self.members:
            self.members.append(username)

    def remove_member(self, username: str) -> None:
        # remove the user if they are in the room
        if username in self.members:
            self.members.remove(username)

    def can_join(self, username: str) -> bool:
        # subclasses decide who is allowed to join
        raise NotImplementedError

    # message history methods

    def add_message(self, message: BaseMessage) -> None:
        # add a new message to the room history
        self.history.append(message)

    def message_generator(self):
        # yield each message in the history one at a time (APC requirement: generator)
        for message in self.history:
            yield message

    def get_history_dicts(self) -> list[dict]:
        # use the generator to build a list of dictionaries (APC requirement: list comprehension)
        return [msg.to_dict() for msg in self.message_generator()]

    def to_dict(self) -> dict:
        # return the room info as a plain dictionary
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "members": self.members,
            "message_count": len(self.history),
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, members={len(self.members)})"
        )


class PublicRoom(BaseRoom):
    """
    A public room that any logged-in user can join.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)

    def can_join(self, username: str) -> bool:
        # public rooms are always open
        return True


class PrivateRoom(BaseRoom):
    """
    A private room that only invited users can join.

    Attributes:
        owner   (str):       the username of whoever created the room
        invited (list[str]): usernames that are allowed to enter
    """

    def __init__(self, name: str, owner: str) -> None:
        super().__init__(name)
        self.owner: str = owner
        self.invited: list[str] = [owner]  # the owner is always on the invite list

    def invite(self, username: str) -> None:
        # add a user to the invite list if they are not already on it
        if username not in self.invited:
            self.invited.append(username)

    def can_join(self, username: str) -> bool:
        # only users on the invite list can join
        return username in self.invited

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["owner"] = self.owner
        data["invited"] = self.invited
        return data
