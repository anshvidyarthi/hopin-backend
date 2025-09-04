from flask import Blueprint, request, jsonify, g
from ..auth.utils import token_required
from ..models import db, Notification
from datetime import datetime

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

@notifications_bp.route("", methods=["GET"])
@token_required
def get_notifications():
    """Get user's notifications with pagination"""
    profile = g.current_user
    
    page = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 20, type=int), 50)
    unread_only = request.args.get("unread_only", False, type=bool)
    
    query = Notification.query.filter_by(user_id=profile.id)
    
    if unread_only:
        query = query.filter_by(read=False)
    
    notifications = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    
    total_unread = Notification.query.filter_by(user_id=profile.id, read=False).count()
    
    return jsonify({
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "ride_id": n.ride_id,
                "request_id": n.request_id,
                "message_id": n.message_id,
                "other_user_id": n.other_user_id,
                "action_data": n.action_data,
                "read": n.read,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None
            }
            for n in notifications
        ],
        "total_unread": total_unread,
        "has_more": len(notifications) == limit
    })

@notifications_bp.route("/<notification_id>/read", methods=["POST"])
@token_required
def mark_notification_read(notification_id):
    """Mark specific notification as read"""
    profile = g.current_user
    
    notification = Notification.query.filter_by(
        id=notification_id, 
        user_id=profile.id
    ).first()
    
    if not notification:
        return jsonify({"error": "Notification not found"}), 404
    
    if not notification.read:
        notification.read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
    
    return jsonify({"message": "Notification marked as read"})

@notifications_bp.route("/mark_all_read", methods=["POST"])
@token_required
def mark_all_read():
    """Mark all user notifications as read"""
    profile = g.current_user
    
    unread_notifications = Notification.query.filter_by(
        user_id=profile.id,
        read=False
    ).all()
    
    for notification in unread_notifications:
        notification.read = True
        notification.read_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        "message": f"Marked {len(unread_notifications)} notifications as read"
    })

@notifications_bp.route("/<notification_id>", methods=["DELETE"])
@token_required
def delete_notification(notification_id):
    """Delete specific notification"""
    profile = g.current_user
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=profile.id
    ).first()
    
    if not notification:
        return jsonify({"error": "Notification not found"}), 404
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({"message": "Notification deleted"})

@notifications_bp.route("/clear_all", methods=["DELETE"])
@token_required
def clear_all_notifications():
    """Clear all user notifications"""
    profile = g.current_user
    
    deleted_count = Notification.query.filter_by(user_id=profile.id).delete()
    db.session.commit()
    
    return jsonify({
        "message": f"Cleared {deleted_count} notifications"
    })