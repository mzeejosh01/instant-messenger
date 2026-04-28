"""
server/models/chatroom.py - Room class hierarchy.

BaseRoom    (parent)
├── PublicRoom   — open to all connected users
└── PrivateRoom  — restricted to an invite list, has an owner

Inheritance is used because every room type shares a name, member
list, message history, and core join/leave/broadcast behaviour.
Subclasses only differ in their access-control logic.
"""

from __future__ import annotations
from server.models.message import BaseMessage


class BaseRoom:
    """
    Parent class for all room types.

    Attributes:
        name    (str):              Unique room identifier.
        members (list[str]):        Usernames of currently present users.
        history (list[BaseMessage]):Ordered message log for this room.
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.members: list[str] = []
        self.history: list[BaseMessage] = []

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def add_member(self, username: str) -> None:
        """Add *username* if not already a member."""
        if username not in self.members:
            self.members.append(username)

    def remove_member(self, username: str) -> None:
        """Remove *username* if present."""
        if username in self.members:
            self.members.remove(username)

    # ------------------------------------------------------------------
    # Access control (overridden by subclasses)
    # ------------------------------------------------------------------

    def can_join(self, username: str) -> bool:
        """Return True if *username* is allowed to join this room."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Message log
    # ------------------------------------------------------------------

    def add_message(self, message: BaseMessage) -> None:
        """Append a message to the room history."""
        self.history.append(message)

    def get_history_dicts(self) -> list[dict]:
        """Return message history as a list of serialisable dicts.
        Uses list comprehension (APC requirement).
        """
        return [msg.to_dict() for msg in self.history]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
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
    A public room — any logged-in user may join.
    No additional attributes beyond BaseRoom.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)

    def can_join(self, username: str) -> bool:
        """Public rooms are always joinable."""
        return True


class PrivateRoom(BaseRoom):
    """
    A private room — only users on the invite list may join.

    Attributes:
        owner   (str):       Username of the creator (auto-invited).
        invited (list[str]): Usernames permitted to enter.
    """

    def __init__(self, name: str, owner: str) -> None:
        super().__init__(name)
        self.owner: str = owner
        self.invited: list[str] = [owner]   # owner is always invited

    def invite(self, username: str) -> None:
        """Grant *username* permission to join this room."""
        if username not in self.invited:
            self.invited.append(username)

    def can_join(self, username: str) -> bool:
        """Only invited users may join a private room."""
        return username in self.invited

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["owner"] = self.owner
        data["invited"] = self.invited
        return data
