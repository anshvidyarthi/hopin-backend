import jwt
import datetime
import os
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

from functools import wraps
import jwt
from flask import request

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "Missing token"}, 401

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return {"error": "Token expired"}, 401
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}, 401

        request.user_id = payload["user_id"]
        return f(*args, **kwargs)
    return wrapper