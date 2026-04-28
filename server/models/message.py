"""
server/models/message.py - Message class hierarchy.

BaseMessage  (parent)
├── TextMessage   — plain text chat message
└── ImageMessage  — base64-encoded image with optional caption

Inheritance is used here because every message type shares a sender,
room, timestamp, and serialisation interface, while each subclass
adds only its own payload fields.
"""

from datetime import datetime, timezone


class BaseMessage:
    """
    Parent class for all message types.

    Attributes:
        sender    (str): Username of the message author.
        room      (str): Name of the destination room.
        timestamp (str): UTC time the message was created (HH:MM format).
    """

    def __init__(self, sender: str, room: str) -> None:
        self.sender: str = sender
        self.room: str = room
        # Store a human-readable time string for display in the GUI
        self.timestamp: str = datetime.now(timezone.utc).strftime("%H:%M")

    def to_dict(self) -> dict:
        """
        Serialise shared fields to a dict.
        Subclasses call super().to_dict() and extend the result.
        """
        return {
            "type": self.__class__.__name__,
            "sender": self.sender,
            "room": self.room,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"sender={self.sender!r}, room={self.room!r}, ts={self.timestamp!r})"
        )


class TextMessage(BaseMessage):
    """
    A plain-text chat message.

    Inherits sender / room / timestamp from BaseMessage.

    Attributes:
        content (str): The text body of the message.
    """

    def __init__(self, sender: str, room: str, content: str) -> None:
        super().__init__(sender, room)
        self.content: str = content

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["content"] = self.content
        return data


class ImageMessage(BaseMessage):
    """
    A message carrying an image encoded as a base64 data-URI string.

    Inherits sender / room / timestamp from BaseMessage.

    Attributes:
        image_data (str): Base64-encoded image (e.g. "data:image/png;base64,...").
        caption    (str): Optional caption shown below the image.
    """

    def __init__(
        self, sender: str, room: str, image_data: str, caption: str = ""
    ) -> None:
        super().__init__(sender, room)
        self.image_data: str = image_data
        self.caption: str = caption

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["image_data"] = self.image_data
        data["caption"] = self.caption
        return data
