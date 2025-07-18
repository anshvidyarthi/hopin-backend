from flask import Flask
from flask_cors import CORS
from backend.models import db
from backend.routes.api import api_blueprint
from backend.routes.auth import auth_bp
from backend.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object('backend.config.Config')

    CORS(app)
    db.init_app(app)

    app.register_blueprint(api_blueprint, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    return app
