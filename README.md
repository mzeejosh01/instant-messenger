# APC Instant Messenger
**Advanced Programming Concepts — VUB 2025-2026**

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python Main.py
```

That's it — one command starts both the server and the GUI.

## Architecture

```
Main.py                     # Entry point
server/
  app.py                    # Flask-SocketIO factory
  socket_handler.py         # All server-side events + RoomManager
  models/
    user.py                 # User class
    message.py              # BaseMessage, TextMessage, ImageMessage
    chatroom.py             # BaseRoom, PublicRoom, PrivateRoom
client/
  app.py                    # MessengerApp (root Tk window + socket)
  login_screen.py           # Login frame
  chat_screen.py            # Main chat frame
```

## Features (current)
- Connect to server with a chosen username
- Join public rooms (#general, #random)
- Send and receive text messages in real time
- Send images (PNG/JPG/GIF) — displayed inline if Pillow is installed
- Create private rooms
- Invite users to private rooms
- Member list per room
- Message history when joining a room

## OOP structure
| Class | Inherits from | Purpose |
|---|---|---|
| `User` | — | Connected client |
| `BaseMessage` | — | Shared message fields |
| `TextMessage` | `BaseMessage` | Text chat message |
| `ImageMessage` | `BaseMessage` | Image message |
| `BaseRoom` | — | Shared room logic |
| `PublicRoom` | `BaseRoom` | Open to all |
| `PrivateRoom` | `BaseRoom` | Invite-only |
