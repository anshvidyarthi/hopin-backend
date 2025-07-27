from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from backend.models import db, Message
from backend.auth.utils import verify_jwt_token_for_socket
import datetime

# Initialize with your Flask app elsewhere like: socketio.init_app(app)
socketio = SocketIO(cors_allowed_origins="*")

# Maps Socket IDs to user IDs for easy lookup
socket_user_map = {}

@socketio.on("connect")
def handle_connect(auth):
    token = auth.get("token") if auth else None
    user = verify_jwt_token_for_socket(token)

    if not user:
        print("Unauthorized socket attempt.")
        disconnect()
        return

    user_id = user["id"]
    sid = request.sid
    socket_user_map[sid] = user_id
    join_room(f"user:{user_id}")
    print(f"User {user_id} connected and joined room user:{user_id}")


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    user_id = socket_user_map.pop(sid, None)
    if user_id:
        leave_room(f"user:{user_id}")
        print(f"User {user_id} disconnected and left room user:{user_id}")


@socketio.on("send_message")
def handle_send_message(data):
    sid = request.sid
    sender_id = socket_user_map.get(sid)

    if not sender_id:
        print("Unknown sender.")
        disconnect()
        return

    receiver_id = data.get("to")
    ride_id = data.get("ride_id")
    content = data.get("message")

    if not receiver_id or not content or not ride_id:
        emit("error", {"error": "Missing 'to', 'ride_id', or 'message'."})
        return

    # Save message
    message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        ride_id=ride_id,
        content=content,
        created_at=datetime.datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()

    # Construct conversation room name
    room = f"conversation:{ride_id}:{min(sender_id, receiver_id)}:{max(sender_id, receiver_id)}"

    # Emit to all participants in room
    payload = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "ride_id": ride_id,
        "content": content,
        "created_at": message.created_at.isoformat()
    }
    emit("receive_message", payload, room=room)

    # Optionally echo back just to sender
    emit("message_sent", payload)


@socketio.on("join_room")
def handle_join(data):
    room = data.get("room")
    if not room:
        emit("error", {"error": "Missing room"})
        return

    join_room(room)
    emit("joined_room", {"room": room})
    print(f"{request.sid} joined {room}")
