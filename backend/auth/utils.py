import jwt
import datetime
import os
import uuid
from flask import jsonify, request, g
from functools import wraps
from dotenv import load_dotenv
from ..models import db, Profile
from sqlalchemy.exc import SQLAlchemyError

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


JWT_ALGOS = ["HS256"]

def _unauthorized(msg: str, code: str = "invalid_token", status: int = 401):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    resp.headers["WWW-Authenticate"] = f'Bearer error="{code}"'
    return resp

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return _unauthorized("Missing or invalid Authorization header", "invalid_request")

        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
        except jwt.ExpiredSignatureError:
            return _unauthorized("Token expired", "token_expired")
        except jwt.InvalidTokenError:
            return _unauthorized("Invalid token", "invalid_token")

        profile_id = payload.get("profile_id")
        if not profile_id:
            return _unauthorized("Token missing subject", "invalid_token")

        try:
            # SQLAlchemy 2.x: prefer db.session.get(Model, pk)
            profile = db.session.get(Profile, profile_id)
        except SQLAlchemyError:
            # If the DB is down, say 503—this helps you distinguish infra from auth
            return jsonify({"error": "Database unavailable"}), 503

        # Treat non-existent / deactivated / soft-deleted as unauthorized
        if not profile or getattr(profile, "is_deleted", False):
            return _unauthorized("Unauthorized", "invalid_token")

        g.current_user = profile
        return f(*args, **kwargs)
    return decorated