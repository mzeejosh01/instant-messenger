# server/app.py - sets up the Flask server and SocketIO.
#
# This creates the Flask app and SocketIO instance,
# then loads all the event handlers from socket_handler.py.

from flask import Flask
from flask_socketio import SocketIO

from server.socket_handler import RoomManager, register_handlers


def create_server() -> tuple[Flask, SocketIO]:
    # create the Flask app
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "apc-vub-2025-secret"

    # attach SocketIO to the app
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    # one RoomManager shared by all event handlers
    manager = RoomManager()
    register_handlers(socketio, manager)

    return app, socketio
