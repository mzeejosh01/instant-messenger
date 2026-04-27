from flask import Flask, send_from_directory
from flask_socketio import SocketIO

app = Flask(__name__, static_folder="../client", static_url_path="")
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@socketio.on('connect')
def handle_connect():
    print("A user connected!")

@socketio.on('disconnect')
def handle_disconnect():
    print("A user disconnected!")