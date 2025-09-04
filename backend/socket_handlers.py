from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from backend.models import db, Message, Notification
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
        "id": message.id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "ride_id": ride_id,
        "content": content,
        "created_at": message.created_at.isoformat()
    }
    emit("receive_message", payload, room=room)

    # Send notification to receiver (import here to avoid circular import)
    try:
        from backend.services.notifications import NotificationService
        from backend.models import Profile
        
        sender_profile = Profile.query.get(sender_id)
        if sender_profile:
            NotificationService.new_message(receiver_id, message, sender_profile)
    except Exception as e:
        print(f"Error sending message notification: {e}")

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


@socketio.on("mark_notification_read")
def handle_mark_notification_read(data):
    sid = request.sid
    user_id = socket_user_map.get(sid)
    
    if not user_id:
        emit("error", {"error": "Unauthorized"})
        return
    
    notification_id = data.get("notification_id")
    if not notification_id:
        emit("error", {"error": "Missing notification_id"})
        return
    
    # Update notification as read
    notification = Notification.query.filter_by(
        id=notification_id, 
        user_id=user_id
    ).first()
    
    if notification:
        notification.read = True
        notification.read_at = datetime.datetime.utcnow()
        db.session.commit()
        emit("notification_marked_read", {"notification_id": notification_id})


def send_notification_to_user(user_id, notification_type, title, body, **kwargs):
    """
    Internal function to send notifications to users
    Called by backend services, not directly by socket events
    """
    # Create notification in database
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        body=body,
        ride_id=kwargs.get('ride_id'),
        request_id=kwargs.get('request_id'),
        message_id=kwargs.get('message_id'),
        other_user_id=kwargs.get('other_user_id'),
        action_data=kwargs.get('action_data'),
        delivered=False
    )
    
    try:
        db.session.add(notification)
        db.session.commit()
        
        # Emit to user's room if they're connected
        notification_data = {
            "id": notification.id,
            "type": notification.type,
            "title": notification.title,
            "body": notification.body,
            "ride_id": notification.ride_id,
            "request_id": notification.request_id,
            "message_id": notification.message_id,
            "other_user_id": notification.other_user_id,
            "action_data": notification.action_data,
            "created_at": notification.created_at.isoformat()
        }
        
        socketio.emit("receive_notification", notification_data, room=f"user:{user_id}")
        
        # Mark as delivered
        notification.delivered = True
        db.session.commit()
        
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending notification: {e}")
        return None
