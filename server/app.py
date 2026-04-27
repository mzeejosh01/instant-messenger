from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def home():
    return "Server is running"

@socketio.on('connect')
def handle_connect():
    print("A user connected!")

@socketio.on('disconnect')
def handle_disconnect():
    print("A user disconnected!")

if __name__ == '__main__':
    socketio.run(app, debug=True)