import uuid
from flask import Blueprint, g, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth.utils import generate_access_token, generate_auth_response, token_required
from ..models import db, User, Profile
from ..user.upload_image import upload_profile_photo_to_s3

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    emailToLowerCase = data.get("email", "").strip().lower()
    user = User.query.filter_by(email=emailToLowerCase).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    return generate_auth_response(user)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    if email:
        email = email.strip().lower()

    name = request.form.get('name')
    password = request.form.get('password')
    phone = request.form.get('phone')
    photo_file = request.files.get('photo')

    if not all([email, name, password, phone, photo_file]):
        return jsonify({'error': 'Name, email, password, phone, and photo are required'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'User already exists'}), 409

    # Step 1: Create user
    hashed_pw = generate_password_hash(password)
    user = User(email=email, name=name, password_hash=hashed_pw)
    db.session.add(user)
    db.session.commit()

    # Step 2: Pre-generate profile ID (needed for S3 pathing)
    profile_id = str(uuid.uuid4())

    # Step 3: Upload profile photo to S3 using profile_id
    try:
        photo_url = upload_profile_photo_to_s3(photo_file, photo_file.filename, profile_id, name)
    except Exception as e:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'error': 'Failed to upload profile photo', 'details': str(e)}), 500

    # Step 4: Create profile using same ID
    profile = Profile(
        id=profile_id,            # use the manually generated UUID
        user_id=user.id,
        name=name,
        email=email,
        phone=phone,
        photo=photo_url,
        is_onboarded=False
    )
    db.session.add(profile)
    db.session.commit()

    return generate_auth_response(user, profile)

@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    """
    Logout endpoint - currently stateless since we use JWTs.
    In the future, this could invalidate tokens in a blacklist or Redis cache.
    """
    return jsonify({"message": "Logged out successfully"}), 200

@auth_bp.route("/delete", methods=["DELETE"])
@token_required
def delete_account():
    profile = g.current_user
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        db.session.delete(profile)
        db.session.commit()
        response = jsonify({"message": "User account and associated data deleted"})
        return response
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete account", "details": str(e)}), 500