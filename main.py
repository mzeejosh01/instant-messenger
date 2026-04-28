"""
Main.py - Entry point for the Instant Messenger application.

Advanced Programming Concepts - VUB 2025-2026

Run with:  python Main.py

This module starts the Flask-SocketIO server in a background daemon
thread, then launches the Tkinter GUI on the main thread.
Tkinter MUST run on the main thread — that is why the server is
threaded and not the other way around.
"""

import threading
from server.app import create_server
from client.app import launch_client


def start_server() -> None:
    """Create and run the Flask-SocketIO server (blocking call)."""
    app, socketio = create_server()
    socketio.run(app, host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    # Start the server in a background daemon thread.
    # Daemon=True means it will be killed automatically when the GUI closes.
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    print("[Main] Server thread started on http://127.0.0.1:5050")

    # Launch the Tkinter GUI on the main thread (blocking until window closes).
    launch_client()
