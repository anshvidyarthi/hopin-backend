from flask import Blueprint, jsonify, request, g
from ..auth.utils import token_required
from ..models import db, Profile
from .driver import is_verified_driver
from ..user.upload_image import upload_profile_photo_to_s3

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    profile = g.current_user

    return jsonify({
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "photo": profile.photo,
        "rating": profile.rating,
        "total_rides": profile.total_rides,
        "is_driver": is_verified_driver(profile),
        "phone": profile.phone,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
    })

@user_bp.route("/profile", methods=["PATCH"])
@token_required
def update_profile():
    profile = g.current_user
    user = profile.user  # access the related User object

    # Support both JSON and multipart/form-data
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    # Handle photo file
    photo_file = request.files.get("photo")
    if photo_file:
        photo_url = upload_profile_photo_to_s3(photo_file, photo_file.filename, profile.id, profile.name)
        profile.photo = photo_url

    # Fields to update in both Profile and User
    shared_fields = ["name", "email"]
    for field in shared_fields:
        if field in data:
            setattr(profile, field, data[field])
            setattr(user, field, data[field])

    # Fields only in Profile
    for field in ["phone", "rating", "total_rides"]:
        if field in data:
            setattr(profile, field, data[field])

    db.session.commit()

    return jsonify({"message": "Profile and user updated successfully"})