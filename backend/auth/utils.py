import jwt
import datetime
import os
import uuid
from flask import jsonify, request, g
from functools import wraps
from dotenv import load_dotenv
from ..models import db, Session, User, Profile

load_dotenv()
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_EXP_DELTA_SECONDS = 3600  # 1 hour


def generate_access_token(profile_id):
    payload = {
        'profile_id': profile_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token


def create_auth_tokens(user):
    profile = user.profile
    access_token = generate_access_token(profile.id)
    refresh_token = str(uuid.uuid4())

    session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=30),
        user_agent=request.headers.get('User-Agent'),
        ip_address=request.remote_addr
    )
    db.session.add(session)
    db.session.commit()

    return access_token, refresh_token


def generate_auth_response(user, profile=None):
    if not profile:
        profile = user.profile

    access_token, refresh_token = create_auth_tokens(user)

    response_body = {
        "access_token": access_token,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "email": profile.email,
            "photo": profile.photo,
            "phone": profile.phone
        }
    }

    response = jsonify(response_body)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="None",
        secure=True
    )
    return response


def verify_jwt_token_for_socket(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        profile_id = payload.get("profile_id")
        if not profile_id:
            return None
        profile = Profile.query.get(profile_id)
        return {"id": profile.id} if profile else None
    except jwt.ExpiredSignatureError:
        print("Socket token expired.")
    except jwt.InvalidTokenError:
        print("Invalid socket token.")
    return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            profile = Profile.query.get(payload["profile_id"])
            if not profile:
                return jsonify({"error": "User not found"}), 404
            g.current_user = profile
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated