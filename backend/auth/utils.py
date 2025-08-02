import jwt
import datetime
import os
import uuid
from flask import jsonify, request, g
from functools import wraps
from dotenv import load_dotenv
from ..models import db, Profile

load_dotenv()
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_EXP_DELTA_SECONDS = 60 * 60 * 24 * 30 #1 month


def generate_access_token(profile_id):
    payload = {
        'profile_id': profile_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token


def create_auth_token(user):
    profile = user.profile
    access_token = generate_access_token(profile.id)
    return access_token

def generate_auth_response(user, profile=None):
    if not profile:
        profile = user.profile

    access_token = create_auth_token(user)

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

    return jsonify(response_body)


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