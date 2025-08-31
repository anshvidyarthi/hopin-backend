from flask import Blueprint, request, jsonify, g
from sqlalchemy import and_, or_
from ..auth.utils import token_required
from ..models import db, Message, Profile, Ride, RideRequest
from sqlalchemy.orm import aliased

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")

@messages_bp.route("/history", methods=["GET"])
@token_required
def get_message_history():
    other_user_id = request.args.get("with")
    ride_id = request.args.get("ride_id")

    if not other_user_id or not ride_id:
        return jsonify({"error": "Missing 'with' or 'ride_id' query parameter"}), 400

    current_profile_id = g.current_user.id

    messages = Message.query.filter(
        and_(
            Message.ride_id == ride_id,
            or_(
                and_(Message.sender_id == current_profile_id, Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id, Message.receiver_id == current_profile_id)
            )
        )
    ).order_by(Message.created_at.asc()).all()

    return jsonify([
        {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "ride_id": msg.ride_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        for msg in messages
    ])

@messages_bp.route("/conversations", methods=["GET"])
@token_required
def get_conversations():
    current_profile_id = g.current_user.id

    # Subquery: get latest message time per (other_user, ride)
    subq = db.session.query(
        db.case(
            (Message.sender_id == current_profile_id, Message.receiver_id),
            else_=Message.sender_id
        ).label("other_user_id"),
        Message.ride_id,
        db.func.max(Message.created_at).label("last_time")
    ).filter(
        or_(
            Message.sender_id == current_profile_id,
            Message.receiver_id == current_profile_id
        )
    ).group_by("other_user_id", Message.ride_id).subquery()

    # Aliased for joining to actual message
    M = aliased(Message)

    # Main query to get metadata + latest message
    results = db.session.query(
        subq.c.other_user_id,
        subq.c.ride_id,
        subq.c.last_time,
        Profile,
        Ride,
        RideRequest.status.label("request_status"),
        M.content.label("last_message_content"),
        M.sender_id.label("last_message_sender")
    ).join(
        Profile, Profile.id == subq.c.other_user_id
    ).join(
        Ride, Ride.id == subq.c.ride_id
    ).outerjoin(
        RideRequest,
        RideRequest.ride_id == subq.c.ride_id
    ).join(
        M,
        and_(
            M.ride_id == subq.c.ride_id,
            or_(
                and_(M.sender_id == current_profile_id, M.receiver_id == subq.c.other_user_id),
                and_(M.receiver_id == current_profile_id, M.sender_id == subq.c.other_user_id)
            ),
            M.created_at == subq.c.last_time
        )
    ).order_by(
        db.case(
            (RideRequest.status == 'pending', 0),
            else_=1
        ),
        subq.c.last_time.desc()
    ).all()

    conversations = []
    for other_user_id, ride_id, last_time, other_user, ride, request_status, content, sender_id in results:
        conversations.append({
            "otherUser": {
                "id": other_user.id,
                "name": other_user.name,
                "photo": other_user.photo
            },
            "rideId": ride_id,
            "rideDetails": {
                "route": f"{ride.start_location} → {ride.end_location}",
                "date": ride.departure_time.strftime("%Y-%m-%d"),
                "type": "driver" if ride.driver_id == other_user.id else "rider"
            },
            "lastMessage": {
                "content": content,
                "timestamp": last_time.isoformat(),
                "senderId": sender_id
            },
            "status": request_status if request_status else "pending"
        })

    return jsonify(conversations)