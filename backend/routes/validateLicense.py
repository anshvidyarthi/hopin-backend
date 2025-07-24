from flask import Blueprint, request, jsonify, g
from ..auth.utils import token_required
from ..models import db, License, Profile
from ..driver.upload_license import upload_license_to_s3, analyze_image, validate_license_fields, is_name_match
import os

validate_bp = Blueprint("validate", __name__, url_prefix="/validate")

@validate_bp.route("/license", methods=["POST"])
@token_required
def validate_license():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    allowed_types = ["image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        return jsonify({"error": "Unsupported file type. Please upload a JPG or PNG image."}), 400

    user = g.current_user

    s3_url = upload_license_to_s3(file, file.filename, user_id=user.id, user_name=user.name)
    bucket = os.getenv("S3_LICENSES_BUCKET_NAME")
    key = s3_url.split(f"{bucket}.s3.amazonaws.com/")[-1]

    result = analyze_image(bucket, key)
    validation = validate_license_fields(result.get("TextDetections", []))

    if not validation["valid"]:
        return jsonify({"error": validation["error"]}), 400

    if not is_name_match(user.name, validation["name"]):
        return jsonify({
            "error": f"Name mismatch. License name '{validation['name']}' does not match account name '{user.name}'."
        }), 400

    license = License(
        user_id=user.id,
        license_number=validation["license_number"],
        full_name=validation["name"],
        document_url=s3_url,
        expiration_date=validation["expiration_date"],
        validated=True
    )
    db.session.add(license)

    profile = Profile.query.filter_by(user_id=user.id).first()
    if profile:
        profile.is_driver = True
    else:
        return jsonify({"error": "User profile not found"}), 404

    db.session.commit()

    return jsonify({
        "message": "License validated and stored. Driver status updated.",
        "photo_url": s3_url,
        "license_number": validation["license_number"],
        "name": validation["name"]
    })