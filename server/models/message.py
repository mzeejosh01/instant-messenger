# server/models/message.py - message classes.
#
# BaseMessage is the parent class.
# TextMessage and ImageMessage both inherit from it.
# We use inheritance because all messages share sender, room, and timestamp.
# Each subclass just adds its own extra data on top.

from datetime import datetime, timezone


class BaseMessage:
    """
    Parent class for all message types.

    Attributes:
        sender    (str): the username of whoever sent the message
        room      (str): the name of the room the message was sent to
        timestamp (str): the time the message was created (HH:MM format)
    """

    def __init__(self, sender: str, room: str) -> None:
        self.sender: str = sender
        self.room: str = room
        # save the current time as a readable string
        self.timestamp: str = datetime.now(timezone.utc).strftime("%H:%M")

    def to_dict(self) -> dict:
        # return the shared fields as a dictionary
        # subclasses call this and then add their own fields
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
    A plain text chat message.

    Inherits sender, room, and timestamp from BaseMessage.

    Attributes:
        content (str): the text the user typed
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
    A message that contains an image encoded as a base64 string.

    Inherits sender, room, and timestamp from BaseMessage.

    Attributes:
        image_data (str): the image encoded as a base64 data URI
        caption    (str): optional text shown below the image
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
