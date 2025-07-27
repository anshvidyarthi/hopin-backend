import uuid
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth.utils import generate_access_token, generate_auth_response, token_required
from ..models import db, User, Session, Profile
from ..user.upload_image import upload_profile_photo_to_s3
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    return generate_auth_response(user)

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "No refresh token"}), 401

    session = Session.query.filter_by(refresh_token=refresh_token).first()
    if not session or session.expires_at < datetime.datetime.utcnow():
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Get the user's profile
    profile = session.user.profile

    if not profile:
        return jsonify({"error": "Associated profile not found"}), 404

    access_token = generate_access_token(profile.id)
    return jsonify({ "access_token": access_token })

@auth_bp.route("/logout", methods=["POST"])
def logout():
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        Session.query.filter_by(refresh_token=refresh_token).delete()
        db.session.commit()

    response = jsonify({ "message": "Logged out" })
    response.set_cookie("refresh_token", "", expires=0)
    return response

@auth_bp.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
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
        photo=photo_url
    )
    db.session.add(profile)
    db.session.commit()

    return generate_auth_response(user, profile)

@auth_bp.route("/delete", methods=["DELETE"])
@token_required
def delete_account():
    profile = g.current_user
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Delete all related sessions and profile (via cascade)
        db.session.delete(profile)
        db.session.commit()
        response = jsonify({"message": "User account and associated data deleted"})
        response.set_cookie("refresh_token", "", expires=0)
        return response
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete account", "details": str(e)}), 500