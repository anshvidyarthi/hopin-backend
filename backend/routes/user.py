from flask import Blueprint, jsonify, request, g
from ..auth.utils import token_required
from ..models import db, Profile

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    user = g.current_user
    profile = Profile.query.filter_by(user_id=user.id).first()

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify({
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "photo": profile.photo,
        "rating": profile.rating,
        "total_rides": profile.total_rides,
        "is_driver": profile.is_driver,
        "phone": profile.phone,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
    })

@user_bp.route("/profile", methods=["POST"])
@token_required
def create_profile():
    user = g.current_user

    if Profile.query.filter_by(user_id=user.id).first():
        return jsonify({"error": "Profile already exists"}), 409

    data = request.get_json()
    profile = Profile(
        user_id=user.id,
        name=data.get("name"),
        email=data.get("email"),
        photo=data.get("photo"),
        rating=data.get("rating", 0.0),
        total_rides=data.get("total_rides", 0),
        is_driver=data.get("is_driver", False),
        phone=data.get("phone")
    )

    db.session.add(profile)
    db.session.commit()

    return jsonify({"message": "Profile created", "profile_id": profile.id}), 201

@user_bp.route("/profile", methods=["PATCH"])
@token_required
def update_profile():
    user = g.current_user
    profile = Profile.query.filter_by(user_id=user.id).first()

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    data = request.get_json()

    # Fields to update in both Profile and User if provided
    shared_fields = ["name", "email"]

    for field in shared_fields:
        if field in data:
            setattr(profile, field, data[field])
            setattr(user, field, data[field])

    # Fields only in Profile
    for field in ["photo", "rating", "total_rides", "is_driver", "phone"]:
        if field in data:
            setattr(profile, field, data[field])

    db.session.commit()

    return jsonify({"message": "Profile and user updated successfully"})