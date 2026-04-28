"""
server/app.py - Flask-SocketIO application factory.

Creates the Flask app and SocketIO instance, then registers all
event handlers from socket_handler.py.
"""

from flask import Flask
from flask_socketio import SocketIO

from server.socket_handler import RoomManager, register_handlers


def create_server() -> tuple[Flask, SocketIO]:
    """
    Build and configure the Flask-SocketIO server.

    Returns:
        tuple: (Flask app, SocketIO instance)
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "apc-vub-2025-secret"

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    # One shared RoomManager for the lifetime of the server
    manager = RoomManager()
    register_handlers(socketio, manager)

    return app, socketio
