from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ..auth.utils import generate_access_token
from ..models import db, User, Session
import uuid
import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = generate_access_token(user.id)
    refresh_token = str(uuid.uuid4())

    # Save refresh token in DB
    session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        user_agent=request.headers.get('User-Agent'),
        ip_address=request.remote_addr
    )
    db.session.add(session)
    db.session.commit()

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

    if not all([email, name, password]):
        return jsonify({'error': 'Name, email, and password required'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'User already exists'}), 409

    hashed_pw = generate_password_hash(password)
    user = User(email=email, name=name, password_hash=hashed_pw)

    db.session.add(user)
    db.session.commit()

    token = generate_access_token(user.id)
    return jsonify({'token': token, 'user': {'id': user.id, 'name': user.name, 'email': user.email}})