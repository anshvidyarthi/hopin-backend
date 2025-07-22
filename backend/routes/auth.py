from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth.utils import generate_access_token, create_auth_tokens, token_required
from ..models import db, User, Session, Profile
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token, refresh_token = create_auth_tokens(user)

    response = jsonify({ "access_token": access_token })
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="Strict")
    return response

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "No refresh token"}), 401

    session = Session.query.filter_by(refresh_token=refresh_token).first()
    if not session or session.expires_at < datetime.datetime.utcnow():
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    access_token = generate_access_token(session.user_id)
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
    print("Request headers:", dict(request.headers))
    print("Request origin:", request.headers.get("Origin"))

    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')
    phone = data.get('phone')
    photo = data.get('photo')

    if not all([email, name, password, phone, photo]):
        return jsonify({'error': 'Name, email, password, phone, and photo are required'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'User already exists'}), 409

    hashed_pw = generate_password_hash(password)
    user = User(email=email, name=name, password_hash=hashed_pw)
    db.session.add(user)
    db.session.commit()

    profile = Profile(
        user_id=user.id,
        name=name,
        email=email,
        phone=phone,
        photo=photo,
    )
    db.session.add(profile)
    db.session.commit()

    access_token, refresh_token = create_auth_tokens(user)

    response = jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        },
        'profile': {
            'id': profile.id,
            'photo': profile.photo,
            'phone': profile.phone
        }
    })
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="Strict")
    return response

@auth_bp.route("/delete", methods=["DELETE"])
@token_required
def delete_account():
    user = g.current_user
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Delete all related sessions and profile (via cascade)
        db.session.delete(user)
        db.session.commit()
        response = jsonify({"message": "User account and associated data deleted"})
        response.set_cookie("refresh_token", "", expires=0)
        return response
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete account", "details": str(e)}), 500