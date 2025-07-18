from flask import Blueprint, jsonify
from ..models import User

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route('/users')
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'email': u.email, 'name': u.name} for u in users])