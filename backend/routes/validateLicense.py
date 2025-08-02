from datetime import datetime
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

    profile = g.current_user

    # Upload to S3 and analyze
    s3_url = upload_license_to_s3(file, file.filename, profile_id=profile.id, user_name=profile.name)
    bucket = os.getenv("S3_LICENSES_BUCKET_NAME")
    key = s3_url.split(f"{bucket}.s3.amazonaws.com/")[-1]
    result = analyze_image(bucket, key)
    validation = validate_license_fields(result.get("TextDetections", []))

    if not validation["valid"]:
        return jsonify({"error": validation["error"]}), 400

    if not is_name_match(profile.name, validation["name"]):
        return jsonify({
            "error": f"Name mismatch. License name '{validation['name']}' does not match account name '{profile.name}'."
        }), 400

    # Determine status based on expiration
    expiration = validation["expiration_date"]
    now = datetime.utcnow()
    status = "VERIFIED" if expiration and expiration > now else "EXPIRED"

    # Create or update license
    license = License.query.filter_by(profile_id=profile.id).first()
    if not license:
        license = License(profile_id=profile.id)
        db.session.add(license)

    license.license_number = validation["license_number"]
    license.full_name = validation["name"]
    license.document_url = s3_url
    license.expiration_date = expiration
    license.validated = True
    license.status = status

    db.session.commit()

    response_data = {
        "photo_url": s3_url,
        "license_number": validation["license_number"],
        "name": validation["name"],
        "status": status,
    }

    if status == "VERIFIED":
        response_data["message"] = "License validated successfully. You are now a verified driver."
    else:
        response_data["message"] = "License uploaded but is expired or invalid for driver verification."

    return jsonify(response_data)