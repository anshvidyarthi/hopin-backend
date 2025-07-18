from flask import Blueprint, jsonify, g
from ..auth.utils import token_required

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/me", methods=["GET"])
@token_required
def get_current_user():
    user = g.current_user
    return jsonify({
        "id": user.id,
        "email": user.email,
        "name": user.name
    })