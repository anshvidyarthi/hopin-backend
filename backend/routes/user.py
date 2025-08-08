from flask import Blueprint, jsonify, request, g
from ..auth.utils import token_required
from ..models import db, Profile
from .driver import is_verified_driver
from ..user.upload_image import upload_profile_photo_to_s3
from ..user.computeProfileRating import compute_average_rating

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    print('executed')
    profile = g.current_user
    print(profile)
    return jsonify({
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "photo": profile.photo,
        "driver_rating": compute_average_rating(profile.id, "driver"),
        "rider_rating": compute_average_rating(profile.id, "rider"),
        "total_rides": profile.total_rides,
        "is_driver": is_verified_driver(profile),
        "phone": profile.phone,
        "is_onboarded": profile.is_onboarded,
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

    # Fields only in Profile (excluding 'rating(s)' which should be computed)
    for field in ["phone", "total_rides"]:
        if field in data:
            setattr(profile, field, data[field])

    if "is_onboarded" in data:
        raw = data["is_onboarded"]
        # accept bools or strings like "true"/"false"/"1"/"0"
        if isinstance(raw, str):
            v = raw.strip().lower()
            val = v in ("true", "1", "yes", "y", "on")
        else:
            val = bool(raw)

        # Optional: only allow setting to True via this endpoint
        if val and not profile.is_onboarded:
            profile.is_onboarded = True
        # else: ignore attempts to unset, or raise 400 if you prefer

    db.session.commit()

    return jsonify({"message": "Profile and user updated successfully"})

@user_bp.route("/public/<profile_id>", methods=["GET"])
@token_required
def get_public_profile(profile_id):
    profile = Profile.query.get(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify({
        "id": profile.id,
        "name": profile.name,
        "photo": profile.photo,
        "driver_rating": compute_average_rating(profile.id, "driver"),
        "rider_rating": compute_average_rating(profile.id, "rider"),
        "total_rides": profile.total_rides,
        "is_driver": is_verified_driver(profile),
        "created_at": profile.created_at.isoformat(),
    })