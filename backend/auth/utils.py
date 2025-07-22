import jwt
import datetime
import os
import uuid
from flask import jsonify, request
from ..models import db, Session
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_EXP_DELTA_SECONDS = 3600  # 1 hour

def generate_access_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token

def create_auth_tokens(user):
    access_token = generate_access_token(user.id)
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
    access_token, refresh_token = create_auth_tokens(user)

    response_body = {
        "access_token": access_token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }

    if profile:
        response_body["profile"] = {
            "id": profile.id,
            "photo": profile.photo,
            "phone": profile.phone
        }

    response = jsonify(response_body)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="Strict",  # or "Lax"/"None" if needed
        secure=False         # True in production with HTTPS
    )
    return response

from flask import request, jsonify, g
from functools import wraps
from ..models import User

JWT_SECRET = os.getenv("JWT_SECRET")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user = User.query.get(payload["user_id"])
            if not user:
                return jsonify({"error": "User not found"}), 404
            g.current_user = user  # Attach to global context
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated