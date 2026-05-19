# Main.py - this is where the program starts.
#
# Advanced Programming Concepts - VUB 2025-2026
#
# Run with:  python Main.py
#
# We start the server in a background thread so it runs at the same time as the GUI.
# Tkinter has to run on the main thread, so the server goes in the background.

import threading
from server.app import create_server
from client.app import launch_client


def start_server() -> None:
    # create and run the server
    app, socketio = create_server()
    socketio.run(app, host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    # start the server in a background thread
    # daemon=True means the server thread stops when the window is closed
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    print("[Main] Server thread started on http://127.0.0.1:5050")

    # start the GUI on the main thread
    launch_client()
